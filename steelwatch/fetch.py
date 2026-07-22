from __future__ import annotations

import ipaddress
import json
import socket
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from .collectors.base import USER_AGENT
from .util import trim_text


def _public_hostname(hostname: str) -> bool:
    if not hostname or hostname.lower() in {"localhost", "localhost.localdomain"}:
        return False
    try:
        addresses = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    for address in addresses:
        value = ipaddress.ip_address(address[4][0])
        if not value.is_global:
            return False
    return True


def safe_get(session: requests.Session, url: str, timeout: int) -> requests.Response:
    current = url
    for _ in range(5):
        parts = urlsplit(current)
        if parts.scheme not in {"http", "https"} or not _public_hostname(parts.hostname or ""):
            raise ValueError("Refusing a non-public URL")
        response = session.get(current, timeout=timeout, allow_redirects=False)
        if response.status_code not in {301, 302, 303, 307, 308}:
            response.raise_for_status()
            return response
        location = response.headers.get("Location")
        if not location:
            response.raise_for_status()
        current = urljoin(current, location)
    raise requests.TooManyRedirects("More than five redirects")


def _json_ld_descriptions(soup: BeautifulSoup) -> list[str]:
    values: list[str] = []
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(node.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                candidates.extend(item for item in graph if isinstance(item, dict))
            for key in ("description", "abstract", "articleBody"):
                value = candidate.get(key)
                if isinstance(value, str) and len(value.strip()) > 40:
                    values.append(value)
    return values


def fetch_page_excerpt(url: str, *, official: bool, timeout: int = 20) -> str:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        }
    )
    response = safe_get(session, url, timeout)
    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        return ""
    if len(response.content) > 8_000_000:
        return ""
    soup = BeautifulSoup(response.text, "html.parser")
    fragments: list[str] = []
    for key in ("description", "og:description", "twitter:description"):
        selector = f'meta[name="{key}"]' if ":" not in key else f'meta[property="{key}"]'
        node = soup.select_one(selector)
        if node and node.get("content"):
            fragments.append(node.get("content", ""))
    fragments.extend(_json_ld_descriptions(soup))

    paragraphs = [" ".join(node.get_text(" ", strip=True).split()) for node in soup.select("p")]
    paragraphs = [value for value in paragraphs if len(value) >= 45]
    if official:
        policy_terms = (
            "china",
            "steel",
            "tariff",
            "quota",
            "anti-dumping",
            "countervailing",
            "safeguard",
            "origin",
            "shall apply",
            "entry into force",
        )
        selected = [
            paragraph for paragraph in paragraphs if any(term in paragraph.lower() for term in policy_terms)
        ]
        fragments.extend(selected[:24] or paragraphs[:12])
        limit = 8_000
    else:
        # For news pages, a metadata description plus a few opening paragraphs is sufficient.
        fragments.extend(paragraphs[:5])
        limit = 3_500
    unique: list[str] = []
    seen: set[str] = set()
    for fragment in fragments:
        cleaned = " ".join(fragment.split())
        fingerprint = cleaned.lower()[:180]
        if len(cleaned) < 35 or fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(cleaned)
    return trim_text("\n".join(unique), limit)
