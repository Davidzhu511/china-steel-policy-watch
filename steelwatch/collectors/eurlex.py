from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
import re

from bs4 import BeautifulSoup

from ..fetch import is_access_block_text
from ..models import RawItem
from ..util import canonical_url, is_rule_relevant, stable_id
from .base import Collector


class EurLexCollector(Collector):
    source_id = "eurlex"
    base_url = "https://eur-lex.europa.eu"
    cellar_sparql_url = "https://publications.europa.eu/webapi/rdf/sparql"
    # Official pre-defined feeds for OJ acts: L legislation and C notices.
    rss_feeds = {
        "L": "https://eur-lex.europa.eu/EN/display-feed.rss?rssId=222",
        "C": "https://eur-lex.europa.eu/EN/display-feed.rss?rssId=221",
    }

    def _collect_rss(self, series, start_date, keywords) -> list[RawItem]:
        """Distinguish a valid feed with no relevant acts from an unavailable feed."""
        found: dict[str, RawItem] = {}
        observed_recent = 0
        for journal_series in series:
            feed_url = self.rss_feeds.get(journal_series)
            if feed_url is None:
                raise ValueError(f"Unknown Official Journal series: {journal_series}")
            response = self.session.get(
                feed_url, headers={"Accept": "application/rss+xml, application/xml"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            if (getattr(response, "status_code", 200) == 202
                    or not response.text.strip()
                    or is_access_block_text(response.text)):
                raise ValueError(f"EUR-Lex {journal_series} RSS is unavailable or access-checked")
            try:
                root = ET.fromstring(response.text)
            except ET.ParseError as exc:
                raise ValueError(f"EUR-Lex {journal_series} RSS is not valid XML") from exc
            if root.tag.lower() != "rss":
                raise ValueError(f"EUR-Lex {journal_series} feed is not RSS")
            dated_in_series = 0
            for entry in root.findall("./channel/item"):
                raw_title = " ".join((entry.findtext("title") or "").split())
                href = (entry.findtext("link") or "").strip()
                date_text = (entry.findtext("pubDate") or "").strip()
                if not raw_title or not href or not date_text:
                    continue
                try:
                    published = parsedate_to_datetime(date_text).astimezone(UTC)
                except (TypeError, ValueError, IndexError, OverflowError):
                    continue
                dated_in_series += 1
                if published.date() < start_date or published.date() > datetime.now(UTC).date():
                    continue
                observed_recent += 1
                title = re.sub(r"^(?:OJ:[LC]_[\w]+|CELEX:[\w]+):\s*", "", raw_title)
                if not is_rule_relevant(title, "", keywords):
                    continue
                target = canonical_url(urljoin(self.base_url, href))
                if not target.startswith(("https://eur-lex.europa.eu/", "http://eur-lex.europa.eu/")):
                    continue
                identifier = stable_id(target, title)
                found[identifier] = RawItem(
                    id=identifier, title=title, url=target,
                    published_at=published.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    source_id=self.source_id, source_name=self.source_name,
                    source_kind="official-law", region="欧洲", country="欧盟",
                    language="en",
                    metadata={"oj_series": journal_series, "official": True,
                              "retrieval": "eurlex-official-rss"},
                )
            if not dated_in_series:
                raise ValueError(f"EUR-Lex {journal_series} RSS contains no dated acts")
        if not observed_recent:
            raise ValueError("EUR-Lex RSS contains no recent dated acts")
        return list(found.values())

    def _collect_cellar(self, start_date, end_date, keywords) -> list[RawItem]:
        query = f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?work ?date ?celex ?title WHERE {{
  ?work cdm:official-journal-act_date_publication ?date ;
        cdm:resource_legal_id_celex ?celex .
  OPTIONAL {{ ?work cdm:work_title ?default_title . }}
  OPTIONAL {{
    ?expression cdm:expression_belongs_to_work ?work ;
                cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> ;
                cdm:expression_title ?english_title .
  }}
  BIND(COALESCE(?english_title, ?default_title) AS ?title)
  FILTER(BOUND(?title))
  FILTER(?date >= "{start_date.isoformat()}"^^xsd:date &&
         ?date <= "{end_date.isoformat()}"^^xsd:date)
}}
ORDER BY DESC(?date)
LIMIT 5000
""".strip()
        response = self.session.get(
            self.cellar_sparql_url,
            params={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=max(self.timeout, 60),
        )
        response.raise_for_status()
        payload = response.json()
        bindings = payload.get("results", {}).get("bindings", [])
        if not isinstance(bindings, list) or not bindings:
            raise ValueError("CELLAR SPARQL returned no dated Official Journal acts")

        found: dict[str, RawItem] = {}
        for binding in bindings:
            title = " ".join(binding.get("title", {}).get("value", "").split())
            celex = binding.get("celex", {}).get("value", "").strip()
            published = binding.get("date", {}).get("value", "").strip()
            if not title or not celex or not published:
                continue
            if not is_rule_relevant(title, "", keywords):
                continue
            target = canonical_url(
                f"{self.base_url}/legal-content/EN/TXT/?uri=CELEX:{celex}"
            )
            identifier = stable_id(target, title)
            found[identifier] = RawItem(
                id=identifier,
                title=title,
                url=target,
                published_at=f"{published}T00:00:00Z",
                source_id=self.source_id,
                source_name=self.source_name,
                source_kind="official-law",
                region="欧洲",
                country="欧盟",
                language="en",
                metadata={
                    "celex": celex,
                    "official": True,
                    "retrieval": "publications-office-cellar-sparql",
                },
            )
        return list(found.values())

    def collect(self) -> list[RawItem]:
        lookback = int(self.config.get("lookback_days", 21))
        series = self.config.get("series", ["L", "C"])
        keywords = self.app_config.get("keywords", {})
        found: dict[str, RawItem] = {}

        today = datetime.now(UTC).date()
        try:
            return self._collect_rss(series, today - timedelta(days=max(lookback - 1, 0)), keywords)
        except Exception as exc:
            self.warnings.append(
                f"EUR-Lex RSS unavailable: {type(exc).__name__}: {str(exc)[:160]}"
            )
        for offset in range(lookback):
            issue_date = today - timedelta(days=offset)
            date_parameter = issue_date.strftime("%d%m%Y")
            for journal_series in series:
                url = f"{self.base_url}/oj/daily-view/{journal_series}-series/default.html"
                response = self.session.get(
                    url,
                    params={"ojDate": date_parameter},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                if (getattr(response, "status_code", 200) == 202
                        or not response.text.strip()
                        or is_access_block_text(response.text)):
                    try:
                        fallback = self._collect_cellar(
                            today - timedelta(days=max(lookback - 1, 0)),
                            today,
                            keywords,
                        )
                    except Exception as exc:
                        raise ValueError(
                            "EUR-Lex daily view unavailable and official CELLAR fallback failed: "
                            f"{type(exc).__name__}: {str(exc)[:180]}"
                        ) from exc
                    self.warnings.append(
                        "EUR-Lex daily view unavailable; used official Publications Office "
                        "CELLAR/SPARQL metadata fallback."
                    )
                    return fallback
                soup = BeautifulSoup(response.text, "html.parser")
                legal_links = soup.select('a[href*="/eli/"], a[href*="/legal-content/"]')
                if not legal_links and "official journal" not in soup.get_text(" ", strip=True).lower():
                    raise ValueError("EUR-Lex response is not an identifiable Official Journal page")
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
