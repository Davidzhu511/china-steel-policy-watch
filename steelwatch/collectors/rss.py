from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from dateutil import parser as date_parser

from ..models import RawItem
from ..util import canonical_url, is_rule_relevant, stable_id
from .base import Collector


def _tag_name(value: str) -> str:
    return value.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, *names: str) -> str:
    wanted = {name.lower() for name in names}
    for child in node:
        if _tag_name(child.tag) in wanted:
            return " ".join("".join(child.itertext()).split())
    return ""


def _entry_link(node: ET.Element) -> str:
    for child in node:
        if _tag_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            rel = child.attrib.get("rel", "alternate")
            if rel in {"alternate", ""}:
                return href
        text = (child.text or "").strip()
        if text:
            return text
    return ""


def _published(value: str) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = date_parser.parse(value)
        except (TypeError, ValueError, OverflowError):
            return datetime.now(UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _source_info(node: ET.Element) -> tuple[str, str]:
    for child in node:
        if _tag_name(child.tag) != "source":
            continue
        name = " ".join("".join(child.itertext()).split())
        url = child.attrib.get("url", "")
        return name, url
    return "", ""


class RssCollector(Collector):
    source_id = "rss"

    def _official_match(self, domain: str) -> tuple[bool, str]:
        registry = self.app_config.get("official_domains", {})
        for official_domain, country in registry.items():
            if domain == official_domain or domain.endswith(f".{official_domain}"):
                return True, country
        return False, ""

    def collect(self) -> list[RawItem]:
        lookback_days = int(self.config.get("lookback_days", 10))
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
        keywords = self.app_config.get("keywords", {})
        found: dict[str, RawItem] = {}

        default_limit = max(1, min(50, int(self.config.get("max_items_per_feed", 12))))
        for feed in self.config.get("feeds", []):
            url = str(feed.get("url") or "").strip()
            if not url:
                continue
            response = self.session.get(url, timeout=max(self.timeout, 35))
            response.raise_for_status()
            root = ET.fromstring(response.content)
            nodes = [
                node
                for node in root.iter()
                if _tag_name(node.tag) in {"item", "entry"}
            ]
            accepted = 0
            feed_limit = max(1, min(50, int(feed.get("max_items", default_limit))))
            for node in nodes:
                title = _child_text(node, "title")
                excerpt = _child_text(node, "description", "summary", "content")
                if not title or not is_rule_relevant(title, excerpt, keywords):
                    continue
                published = _published(
                    _child_text(node, "pubdate", "published", "updated", "date")
                )
                if published < cutoff:
                    continue
                target = canonical_url(_entry_link(node))
                if not target:
                    continue

                item_source_name, source_url = _source_info(node)
                source_domain = (
                    urlsplit(source_url or target).hostname or ""
                ).lower().removeprefix("www.")
                official, official_country = self._official_match(source_domain)
                if feed.get("official") is True:
                    official = True
                country = (
                    official_country
                    or str(feed.get("country") or "")
                    or "全球"
                )
                region = str(feed.get("region") or "") or (
                    "欧洲" if country in {"欧盟", "英国", "德国", "法国", "意大利", "西班牙", "土耳其"}
                    else "北美" if country in {"美国", "加拿大"}
                    else "亚洲" if country in {"中国", "印度", "日本", "韩国", "越南"}
                    else "全球"
                )
                source_name = (
                    item_source_name
                    or str(feed.get("name") or "")
                    or source_domain
                    or self.source_name
                )
                identifier = stable_id(target, title)
                found[identifier] = RawItem(
                    id=identifier,
                    title=title,
                    url=target,
                    published_at=published.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    source_id=self.source_id,
                    source_name=source_name,
                    source_kind="official-notice" if official else "news",
                    region=region,
                    country=country,
                    excerpt=excerpt,
                    language=str(feed.get("language") or "en"),
                    metadata={
                        "domain": source_domain,
                        "official": official,
                        "discovery": "rss",
                    },
                )
                accepted += 1
                if accepted >= feed_limit:
                    break
        return list(found.values())
