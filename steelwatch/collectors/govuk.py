from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

from ..models import RawItem
from ..util import canonical_url, is_rule_relevant, parse_datetime, stable_id
from .base import Collector


class GovUkCollector(Collector):
    source_id = "govuk"
    endpoint = "https://www.gov.uk/api/search.json"
    base_url = "https://www.gov.uk"

    def collect(self) -> list[RawItem]:
        lookback = int(self.config.get("lookback_days", 30))
        cutoff = datetime.now(UTC) - timedelta(days=lookback)
        keywords = self.app_config.get("keywords", {})
        found: dict[str, RawItem] = {}

        for query in self.config.get("queries", ["China steel"]):
            response = self.session.get(
                self.endpoint,
                params={"q": query, "count": 100, "order": "-public_timestamp"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            for record in response.json().get("results", []):
                published = parse_datetime(
                    record.get("public_timestamp")
                    or record.get("first_published_at")
                    or record.get("updated_at")
                )
                if published < cutoff:
                    continue
                title = record.get("title") or ""
                excerpt = record.get("description") or record.get("summary") or ""
                if not is_rule_relevant(title, excerpt, keywords):
                    continue
                target = canonical_url(urljoin(self.base_url, record.get("link") or ""))
                if not target:
                    continue
                identifier = stable_id(target, title)
                found[identifier] = RawItem(
                    id=identifier,
                    title=title,
                    url=target,
                    published_at=published.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    source_id=self.source_id,
                    source_name=self.source_name,
                    source_kind="official-notice",
                    region="欧洲",
                    country="英国",
                    excerpt=excerpt,
                    language="en",
                    metadata={
                        "content_id": record.get("content_id", ""),
                        "format": record.get("format", ""),
                        "official": True,
                    },
                )
        return list(found.values())
