from __future__ import annotations

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
    if country in {"德国", "法国", "意大利", "西班牙", "英国", "土耳其"}:
        return "欧洲"
    if country in {"中国", "印度", "日本", "韩国"}:
        return "亚洲"
    if country in {"摩洛哥", "埃及", "阿尔及利亚"}:
        return "非洲"
    if country in {"澳大利亚"}:
        return "大洋洲"
    if country in {"巴西"}:
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

    def collect(self) -> list[RawItem]:
        lookback = int(self.config.get("lookback_days", 7))
        max_records = int(self.config.get("max_records_per_query", 100))
        keywords = self.app_config.get("keywords", {})
        found: dict[str, RawItem] = {}

        for query in self.config.get("queries", []):
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
            response.raise_for_status()
            payload = response.json()
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
                    metadata={"domain": domain, "official": official},
                )
        return list(found.values())
