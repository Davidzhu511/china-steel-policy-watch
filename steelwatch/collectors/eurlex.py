from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import RawItem
from ..util import canonical_url, is_rule_relevant, stable_id
from .base import Collector


class EurLexCollector(Collector):
    source_id = "eurlex"
    base_url = "https://eur-lex.europa.eu"

    def collect(self) -> list[RawItem]:
        lookback = int(self.config.get("lookback_days", 21))
        series = self.config.get("series", ["L", "C"])
        keywords = self.app_config.get("keywords", {})
        found: dict[str, RawItem] = {}

        for offset in range(lookback):
            issue_date = datetime.now(UTC).date() - timedelta(days=offset)
            date_parameter = issue_date.strftime("%d%m%Y")
            for journal_series in series:
                url = f"{self.base_url}/oj/daily-view/{journal_series}-series/default.html"
                response = self.session.get(
                    url,
                    params={"ojDate": date_parameter},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.select("a[href]"):
                    title = " ".join(link.get_text(" ", strip=True).split())
                    href = link.get("href", "")
                    if len(title) < 35:
                        continue
                    if not ("/eli/" in href or "/legal-content/" in href):
                        continue
                    if not is_rule_relevant(title, "", keywords):
                        continue
                    target = canonical_url(urljoin(self.base_url, href))
                    identifier = stable_id(target, title)
                    found[identifier] = RawItem(
                        id=identifier,
                        title=title,
                        url=target,
                        published_at=f"{issue_date.isoformat()}T00:00:00Z",
                        source_id=self.source_id,
                        source_name=self.source_name,
                        source_kind="official-law",
                        region="欧洲",
                        country="欧盟",
                        language="en",
                        metadata={"oj_series": journal_series, "official": True},
                    )
        return list(found.values())
