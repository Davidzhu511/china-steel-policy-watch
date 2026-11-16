"""Competing-origin steel measures must survive discovery without a China keyword."""
import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from steelwatch.collectors.ec_watch_pages import EcWatchPagesCollector
from steelwatch.collectors.eurlex import EurLexCollector
from steelwatch.collectors.rss import RssCollector
from steelwatch.util import is_rule_relevant


CONFIG = json.loads((Path(__file__).parents[1] / "config/sources.json").read_text())
LEGAL_TITLE = (
    "Commission Implementing Regulation (EU) 2026/2547 imposing a definitive "
    "anti-dumping duty on imports of certain cold-rolled flat steel products "
    "originating in India, Japan, Taiwan, Türkiye and Vietnam"
)


@pytest.mark.parametrize("title", [
    LEGAL_TITLE,
    "EU terminates anti-dumping investigation on hot-rolled steel from Türkiye",
    "UK extends countervailing duties on Indian stainless steel bars",
    "Canada opens expiry review of steel plate duties from Japan",
    "US opens anti–circumvention inquiry into Vietnamese steel pipe",
    "Egypt removes steel import tariffs",
    "Morocco reviews safeguards on steel tubes",
    "EU revises rules of origin for steel quotas",
    "欧盟对印度、日本、台湾、土耳其及越南冷轧钢材征收最终反倾销税",
    "China's steelmakers announce new capacity plans",
])
def test_competing_origins_are_in_scope(title):
    assert is_rule_relevant(title, "", CONFIG["keywords"])


@pytest.mark.parametrize("title", [
    "EU imposes anti-dumping duties on ceramic tiles from India",
    "EU reviews import tariffs for environmental protection",
    "US imposes anti-dumping duty on cold-rolled aluminium",
    "Japan steel company investigates an office theft",
])
def test_broader_scope_still_rejects_nonsteel_or_unrelated_stories(title):
    assert not is_rule_relevant(title, "", CONFIG["keywords"])


class Response:
    status_code = 200

    def __init__(self, text):
        self.text = text
        self.content = text.encode()

    def raise_for_status(self):
        pass


class Session:
    def __init__(self, text):
        self.response = Response(text)

    def get(self, *args, **kwargs):
        return self.response


def test_official_rss_and_news_discovery_keep_third_country_law():
    now = datetime.now(UTC).replace(microsecond=0)
    url = "https://eur-lex.europa.eu/eli/reg_impl/2026/2547/oj/eng"
    feed = f"""<rss><channel><item>
      <title>{escape(LEGAL_TITLE)}</title><link>{url}</link>
      <pubDate>{format_datetime(now)}</pubDate>
      </item><item><title>Anti-dumping duties on ceramic tiles from India</title>
      <link>https://eur-lex.europa.eu/eli/reg_impl/2026/9999/oj/eng</link>
      <pubDate>{format_datetime(now)}</pubDate></item></channel></rss>"""
    eurlex = EurLexCollector({"name": "EUR-Lex"}, CONFIG)
    eurlex.session = Session(feed)
    legal = eurlex._collect_rss(["L"], (now - timedelta(days=1)).date(), CONFIG["keywords"])
    assert [item.url for item in legal] == [url]
    rss = RssCollector({"feeds": [{"url": "https://example.com/rss"}]}, CONFIG)
    rss.session = Session(feed)
    assert [item.url for item in rss.collect()] == [url]


def test_trade_watch_page_keeps_competing_origin_steel_and_rejects_other_sectors():
    today = datetime.now(UTC).strftime("%d %B %Y")
    html = f"""<article><h3><a href="/news/steel-duty">{LEGAL_TITLE}</a></h3>
      <p>{today}</p></article>
      <article><h3><a href="/news/tiles-duty">Anti-dumping duty on ceramic tiles
      from India</a></h3><p>{today}</p></article>"""
    page = next(p for p in CONFIG["sources"]["ec_watch_pages"]["pages"]
                if p["name"] == "DG TRADE · Steel")
    collector = EcWatchPagesCollector({"pages": [page]}, CONFIG)
    collector.session = Session(html)
    assert [item.url for item in collector.collect()] == [
        "https://policy.trade.ec.europa.eu/news/steel-duty"
    ]
