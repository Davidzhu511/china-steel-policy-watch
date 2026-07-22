from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..models import RawItem
from ..util import canonical_url, is_rule_relevant, stable_id
from .base import Collector


class FederalRegisterCollector(Collector):
    source_id = "federal_register"
    endpoint = "https://www.federalregister.gov/api/v1/documents.json"

    def collect(self) -> list[RawItem]:
        lookback = int(self.config.get("lookback_days", 21))
        start_date = (datetime.now(UTC).date() - timedelta(days=lookback)).isoformat()
        keywords = self.app_config.get("keywords", {})
        found: dict[str, RawItem] = {}

        for query in self.config.get("queries", ["China steel"]):
            response = self.session.get(
                self.endpoint,
                params={
                    "per_page": 100,
                    "order": "newest",
                    "conditions[term]": query,
                    "conditions[publication_date][gte]": start_date,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            for record in response.json().get("results", []):
                title = record.get("title") or ""
                excerpt = record.get("abstract") or ""
                if not is_rule_relevant(title, excerpt, keywords):
                    continue
                target = canonical_url(record.get("html_url") or record.get("pdf_url") or "")
                if not target:
                    continue
                identifier = stable_id(target, title)
                agencies = [agency.get("name", "") for agency in record.get("agencies", [])]
                found[identifier] = RawItem(
                    id=identifier,
                    title=title,
                    url=target,
                    published_at=f"{record.get('publication_date', start_date)}T00:00:00Z",
                    source_id=self.source_id,
                    source_name=self.source_name,
                    source_kind="official-notice",
                    region="北美",
                    country="美国",
                    excerpt=excerpt,
                    language="en",
                    metadata={
                        "document_number": record.get("document_number", ""),
                        "document_type": record.get("type", ""),
                        "agencies": agencies,
                        "official": True,
                    },
                )
        return list(found.values())
