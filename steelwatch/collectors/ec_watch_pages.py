from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, unquote_plus, urljoin, urlsplit

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
GENERIC_LINK_PREFIXES = (
    "download",
    "english",
    "read more",
    "learn more",
    "find out",
    "see all",
    "skip to",
    "more",
    "view",
    "document",
    "pdf",
)


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def _extract_date(text: str) -> datetime | None:
    matches = sorted(
        (match for pattern in DATE_PATTERNS for match in pattern.finditer(text)),
        key=lambda match: match.start(),
    )
    for match in matches:
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
    fallback = None
    for parent in anchor.parents:
        if getattr(parent, "name", None) not in {"article", "li", "div", "section"}:
            continue
        text = _clean(parent.get_text(" ", strip=True))
        if not 20 <= len(text) <= 900:
            continue
        if fallback is None:
            fallback = (parent, text)
        if _extract_date(text) is not None:
            return parent, text
    if fallback is not None:
        return fallback
    parent = anchor.parent
    return parent, _clean(parent.get_text(" ", strip=True) if parent else "")


def _generic_link(text: str) -> bool:
    lowered = text.strip().lower()
    return any(lowered.startswith(prefix) for prefix in GENERIC_LINK_PREFIXES)


def _filename_title(target: str) -> str:
    parts = urlsplit(target)
    filename = parse_qs(parts.query).get("filename", [""])[0]
    if not filename:
        return ""
    value = unquote_plus(filename).rsplit("/", 1)[-1]
    value = re.sub(r"\.(?:pdf|html?|xlsx?|docx?|zip)$", "", value, flags=re.IGNORECASE)
    return trim_text(_clean(value.replace("_", " ")), 220)


def _title(anchor, container, target: str) -> str:
    text = _clean(anchor.get_text(" ", strip=True))
    if len(text) >= 8 and not _generic_link(text):
        return trim_text(text, 220)
    filename_title = _filename_title(target)
    if filename_title:
        return filename_title
    if _generic_link(text):
        return ""
    if container is not None:
        heading = container.select_one(
            ".ecl-file__title, [class*='file__title'], h2, h3, h4, h5, strong"
        )
        if heading is not None:
            heading_text = _clean(heading.get_text(" ", strip=True))
            if len(heading_text) >= 8:
                return trim_text(heading_text, 220)
    return trim_text(text, 220)


class EcWatchPagesCollector(Collector):
    source_id = "ec_watch_pages"

    def collect(self) -> list[RawItem]:
        lookback_days = int(self.config.get("lookback_days", 60))
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
        found: dict[str, RawItem] = {}
        successes = 0

        for page in self.config.get("pages", []):
            url = str(page.get("url") or "").strip()
            if not url:
                continue
            try:
                response = self.session.get(url, timeout=max(self.timeout, 35))
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
            except Exception as exc:
                self.warnings.append(f"{url}: {type(exc).__name__}: {str(exc)[:120]}")
                continue
            successes += 1
            terms = [str(term).lower() for term in page.get("match_terms", []) if term]
            match_in_title = bool(page.get("match_in_title", False))
            excluded = [term.lower() for term in page.get("exclude_terms", [])]
            include_paths = [
                str(value).lower()
                for value in page.get("include_paths", [])
                if value
            ]
            max_items = max(1, min(50, int(page.get("max_items", 12))))
            page_found: dict[str, RawItem] = {}
            allowed_domains = {
                str(domain).lower().removeprefix("www.")
                for domain in page.get("allowed_domains", [])
                if domain
            }

            for anchor in soup.select("a[href]"):
                target = canonical_url(urljoin(url, anchor.get("href") or ""))
                if not target:
                    continue
                parts = urlsplit(target)
                domain = (parts.hostname or "").lower().removeprefix("www.")
                if allowed_domains and not any(
                    domain == allowed or domain.endswith(f".{allowed}")
                    for allowed in allowed_domains
                ):
                    continue
                if include_paths and not any(value in parts.path.lower() for value in include_paths):
                    continue

                container, context = _container(anchor)
                title = _title(anchor, container, target)
                if len(title) < 8 or any(term in title.lower() for term in excluded):
                    continue
                haystack = title.lower() if match_in_title else f"{title} {context}".lower()
                if terms and not any(term in haystack for term in terms):
                    continue
                published = _extract_date(context)
                if published is None or published < cutoff:
                    continue
                if published > datetime.now(UTC) + timedelta(days=1):
                    continue

                identifier = stable_id(target, title)
                previous = page_found.get(identifier)
                if previous and published <= datetime.fromisoformat(previous.published_at.replace("Z", "+00:00")):
                    continue
                page_found[identifier] = RawItem(
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
            newest = sorted(
                page_found.values(),
                key=lambda item: item.published_at,
                reverse=True,
            )[:max_items]
            found.update({item.id: item for item in newest})
        if not successes and self.warnings:
            raise RuntimeError("; ".join(self.warnings))
        return list(found.values())
