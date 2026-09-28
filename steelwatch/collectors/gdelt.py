from __future__ import annotations

import time
from urllib.parse import urlsplit

from ..models import RawItem
from ..util import canonical_url, is_rule_relevant, iso_datetime, stable_id
from .base import Collector


COUNTRY_ZH = {
    "China": "中国",
    "United States": "美国",
    "United Kingdom": "英国",
    "Germany": "德国",
    "France": "法国",
    "Italy": "意大利",
    "Spain": "西班牙",
    "India": "印度",
    "Turkey": "土耳其",
    "Canada": "加拿大",
    "Australia": "澳大利亚",
    "Brazil": "巴西",
    "Japan": "日本",
    "South Korea": "韩国",
    "Morocco": "摩洛哥",
    "Egypt": "埃及",
    "Algeria": "阿尔及利亚",
}


def region_for(country: str) -> str:
    if country in {"美国", "加拿大"}:
        return "北美"
    if country in {"德国", "法国", "意大利", "西班牙", "英国", "土耳其", "欧盟"}:
        return "欧洲"
    if country in {"中国", "印度", "日本", "韩国"}:
        return "亚洲"
    if country in {"摩洛哥", "埃及", "阿尔及利亚"}:
        return "非洲"
    if country == "澳大利亚":
        return "大洋洲"
    if country == "巴西":
        return "拉美"
    return "全球"


class GdeltCollector(Collector):
    source_id = "gdelt"
    endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"

    def _official_match(self, domain: str) -> tuple[bool, str]:
        registry = self.app_config.get("official_domains", {})
        for official_domain, country in registry.items():
            if domain == official_domain or domain.endswith(f".{official_domain}"):
                return True, country
        return False, ""

    def _request_query(self, query: str, *, lookback: int, max_records: int) -> dict:
        retries = max(1, min(5, int(self.config.get("retries", 3))))
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = self.session.get(
                    self.endpoint,
                    params={
                        "query": query,
                        "mode": "artlist",
                        "maxrecords": min(max_records, 250),
                        "format": "json",
                        "sort": "datedesc",
                        "timespan": f"{lookback}d",
                    },
                    timeout=max(self.timeout, 35),
                )
                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    retry_after = response.headers.get("Retry-After", "")
                    try:
                        wait = float(retry_after)
                    except (TypeError, ValueError):
                        wait = float(2 ** attempt)
                    wait = max(0.5, min(wait, 8.0))
                    last_error = RuntimeError(f"GDELT HTTP {response.status_code}")
                    if attempt + 1 < retries:
                        time.sleep(wait)
                        continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("GDELT returned a non-object JSON payload")
                return payload
            except Exception as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(min(2 ** attempt, 4))
        assert last_error is not None
        raise last_error

    def collect(self) -> list[RawItem]:
        lookback = int(self.config.get("lookback_days", 7))
        max_records = int(self.config.get("max_records_per_query", 40))
        query_delay = max(0.0, min(3.0, float(self.config.get("query_delay_seconds", 0.8))))
        keywords = self.app_config.get("keywords", {})
        found: dict[str, RawItem] = {}
        errors: list[str] = []
        successful_queries = 0

        queries = list(self.config.get("queries", []))
        for index, query in enumerate(queries):
            try:
                payload = self._request_query(
                    query,
                    lookback=lookback,
                    max_records=max_records,
                )
                successful_queries += 1
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {str(exc)[:140]}")
                continue

            for article in payload.get("articles", []):
                title = article.get("title") or ""
                if not is_rule_relevant(title, "", keywords):
                    continue
                target = canonical_url(article.get("url") or "")
                if not target:
                    continue
                domain = (article.get("domain") or urlsplit(target).hostname or "").lower()
                domain = domain.removeprefix("www.")
                official, official_country = self._official_match(domain)
                raw_country = article.get("sourcecountry") or ""
                country = official_country or COUNTRY_ZH.get(raw_country, raw_country) or "全球"
                identifier = stable_id(target, title)
                image_url = article.get("socialimage") or ""
                if image_url and not image_url.startswith("https://"):
                    image_url = ""
                found[identifier] = RawItem(
                    id=identifier,
                    title=title,
                    url=target,
                    published_at=iso_datetime(article.get("seendate")),
                    source_id=self.source_id,
                    source_name=domain or self.source_name,
                    source_kind="official-notice" if official else "news",
                    region=region_for(country),
                    country=country,
                    language=article.get("language") or "",
                    image_url=image_url,
                    metadata={
                        "domain": domain,
                        "official": official,
                        "discovery": "gdelt",
                    },
                )
            if query_delay and index + 1 < len(queries):
                time.sleep(query_delay)

        if successful_queries == 0 and errors:
            raise RuntimeError("all GDELT queries failed; " + " | ".join(errors[:2]))
        return list(found.values())
