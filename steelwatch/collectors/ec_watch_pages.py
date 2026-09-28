from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from ..models import RawItem
from ..util import canonical_url, stable_id, trim_text
from .base import Collector


DATE_PATTERNS = (
    re.compile(
        r"\b(?:[0-3]?\d)\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:[0-3]?\d)\s+[A-Z][a-z]{2}\s+\([A-Za-z]+\)\s*\d{4}\b"
    ),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
)
GENERIC_LINK_TEXT = {
    "download",
    "english",
    "read more",
    "more",
    "view",
    "document",
    "pdf",
}


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def _extract_date(text: str) -> datetime | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = re.sub(r"\s*\([A-Za-z]+\)\s*", " ", match.group(0))
        try:
            parsed = date_parser.parse(value, dayfirst=True)
        except (TypeError, ValueError, OverflowError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _container(anchor):
    for name in ("article", "li", "div"):
        parent = anchor.find_parent(name)
        if parent is not None:
            text = _clean(parent.get_text(" ", strip=True))
            if 20 <= len(text) <= 1800:
                return parent, text
    parent = anchor.parent
    return parent, _clean(parent.get_text(" ", strip=True) if parent else "")


def _title(anchor, container) -> str:
    text = _clean(anchor.get_text(" ", strip=True))
    if len(text) >= 8 and text.lower() not in GENERIC_LINK_TEXT:
        return trim_text(text, 220)
    if container is not None:
        heading = container.find(["h2", "h3", "h4", "h5", "strong"])
        if heading is not None:
            heading_text = _clean(heading.get_text(" ", strip=True))
            if len(heading_text) >= 8:
                return trim_text(heading_text, 220)
    previous = anchor.find_previous(["h2", "h3", "h4", "h5"])
    if previous is not None:
        previous_text = _clean(previous.get_text(" ", strip=True))
        if len(previous_text) >= 8:
            return trim_text(previous_text, 220)
    return trim_text(text, 220)


class EcWatchPagesCollector(Collector):
    source_id = "ec_watch_pages"

    def collect(self) -> list[RawItem]:
        lookback_days = int(self.config.get("lookback_days", 60))
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
        found: dict[str, RawItem] = {}

        for page in self.config.get("pages", []):
            url = str(page.get("url") or "").strip()
            if not url:
                continue
            response = self.session.get(url, timeout=max(self.timeout, 35))
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            terms = [str(term).lower() for term in page.get("match_terms", []) if term]
            allowed_domains = {
                str(domain).lower().removeprefix("www.")
                for domain in page.get("allowed_domains", [])
                if domain
            }

            for anchor in soup.select("a[href]"):
                target = canonical_url(urljoin(url, anchor.get("href") or ""))
                if not target:
                    continue
                domain = (urlsplit(target).hostname or "").lower().removeprefix("www.")
                if allowed_domains and not any(
                    domain == allowed or domain.endswith(f".{allowed}")
                    for allowed in allowed_domains
                ):
                    continue

                container, context = _container(anchor)
                title = _title(anchor, container)
                if len(title) < 8:
                    continue
                haystack = f"{title} {context}".lower()
                if terms and not any(term in haystack for term in terms):
                    continue
                published = _extract_date(context)
                if published is None or published < cutoff:
                    continue

                identifier = stable_id(target, title)
                found[identifier] = RawItem(
                    id=identifier,
                    title=title,
                    url=target,
                    published_at=published.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    source_id=self.source_id,
                    source_name=str(page.get("name") or self.source_name),
                    source_kind="official-notice",
                    region=str(page.get("region") or "欧洲"),
                    country=str(page.get("country") or "欧盟"),
                    excerpt=trim_text(context, 1600),
                    language=str(page.get("language") or "en"),
                    metadata={
                        "official": True,
                        "scope_relevant": True,
                        "watch_page": url,
                    },
                )
        return list(found.values())
