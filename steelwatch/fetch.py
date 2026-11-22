from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from .collectors.base import USER_AGENT
from .util import canonical_url, trim_text

ACCESS_BLOCK_PHRASES = (
    "your request has been flagged as potentially automated",
    "aggressive automated scraping",
    "please complete the captcha",
    "verify you are human",
    "verify that you're not a robot",
    "verify that you are not a robot",
    "verify you are not a robot",
)


def is_access_block_text(value: str) -> bool:
    lowered = value.lower()
    return any(phrase in lowered for phrase in ACCESS_BLOCK_PHRASES)


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


def safe_get(
    session: requests.Session, url: str, timeout: int, *, stream: bool = False,
) -> requests.Response:
    current = url
    for _ in range(5):
        parts = urlsplit(current)
        if parts.scheme not in {"http", "https"} or not _public_hostname(parts.hostname or ""):
            raise ValueError("Refusing a non-public URL")
        options = {"stream": True} if stream else {}
        response = session.get(current, timeout=timeout, allow_redirects=False, **options)
        if response.status_code not in {301, 302, 303, 307, 308}:
            try:
                response.raise_for_status()
            except requests.HTTPError:
                response.close()
                raise
            return response
        location = response.headers.get("Location")
        if not location:
            response.raise_for_status()
        response.close()
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
    page_text = soup.get_text(" ", strip=True).lower()
    if is_access_block_text(page_text):
        return ""
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
        cleaned = " ".join(BeautifulSoup(fragment, "html.parser").get_text(" ", strip=True).split())
        fingerprint = cleaned.lower()[:180]
        if len(cleaned) < 35 or fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(cleaned)
    return trim_text("\n".join(unique), limit)


_DOCUMENT_LINK = re.compile(r"\.(pdf|docx?|xlsx?|csv|zip)(?:$|[?&#])", re.IGNORECASE)


def _limited_body(response: requests.Response, limit: int) -> bytes:
    body = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        body.extend(chunk)
        if len(body) > limit:
            return b""
    return bytes(body)


def fetch_official_observations(url: str, *, timeout: int) -> dict[str, str]:
    """Fingerprint the substantive page and a bounded set of same-host attachments."""
    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        with safe_get(session, url, timeout, stream=True) as response:
            body = _limited_body(response, 8_000_000)
            target = response.url
            content_type = response.headers.get("Content-Type", "").lower()
        if not body:
            return {}
        if "html" not in content_type:
            if ("pdf" in content_type or content_type.startswith(("application/msword", "application/vnd."))
                    or _DOCUMENT_LINK.search(target)):
                return {"document": hashlib.sha256(body).hexdigest()}
            return {}
        soup = BeautifulSoup(body, "html.parser")
        main = soup.select_one("main article, main, article, [role=main]")
        if main is None:
            return {}
        for node in main.select("nav, footer, script, style, aside, form"):
            node.decompose()
        content = " ".join(main.get_text(" ", strip=True).split())
        if not content or is_access_block_text(content):
            return {}
        links = sorted({
            canonical_url(urljoin(target, node["href"]))
            for node in main.select("a[href]")
            if _DOCUMENT_LINK.search(node["href"]) or node.has_attr("download")
        } - {""})
        digest = hashlib.sha256(json.dumps([content, links], ensure_ascii=False).encode()).hexdigest()
        observations = {"document": digest}
        attachments = [link for link in links if urlsplit(link).hostname == urlsplit(canonical_url(target)).hostname]
        for link in attachments[:2]:
            try:
                with safe_get(session, link, min(timeout, 8), stream=True) as response:
                    attachment = _limited_body(response, 4_000_000)
                    attachment_type = response.headers.get("Content-Type", "").lower()
                if attachment and "html" not in attachment_type:
                    observations["attachment:" + link] = hashlib.sha256(attachment).hexdigest()
            except (requests.RequestException, ValueError):
                continue
        return observations
