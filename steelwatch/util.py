from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dateutil import parser as date_parser


TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "source",
}


def canonical_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if not parts.hostname:
        return ""
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if parts.port and parts.port not in {80, 443}:
        host = f"{host}:{parts.port}"
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=False):
        lower = key.lower()
        if lower.startswith("utm_") or lower in TRACKING_PARAMS:
            continue
        query.append((key, value))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower() or "https", host, path, urlencode(query), ""))


def stable_id(url: str, title: str = "") -> str:
    basis = canonical_url(url) if url else normalize_text(title)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]


def normalize_text(value: str) -> str:
    value = re.sub(r"[\u2010-\u2015]", "-", value or "")
    value = re.sub(r"[^\w\u4e00-\u9fff]+", " ", value.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def parse_datetime(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = date_parser.parse(str(value))
        except (ValueError, TypeError, OverflowError):
            parsed = datetime.now(UTC)
    else:
        parsed = datetime.now(UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso_datetime(value: str | datetime | None) -> str:
    return parse_datetime(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def contains_any(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def is_rule_relevant(title: str, excerpt: str, keywords: dict[str, list[str]]) -> bool:
    haystack = f"{title} {excerpt}".lower()
    if contains_any(haystack, keywords.get("exclude", [])):
        return False
    if contains_any(haystack, keywords.get("universal_policy", [])):
        return True
    has_material = contains_any(haystack, keywords.get("materials", []))
    if not has_material:
        return False
    has_china = contains_any(haystack, keywords.get("china", []))
    is_global_steel_rule = contains_any(haystack, keywords.get("global_steel_policy", []))
    return has_china or is_global_steel_rule


def token_set(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if len(token) > 1}


def title_similarity(left: str, right: str) -> float:
    a, b = token_set(left), token_set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def hostname(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def trim_text(value: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"
