import json
from pathlib import Path

from steelwatch.collectors.ec_have_your_say import EcHaveYourSayCollector
from steelwatch.collectors.ec_watch_pages import EcWatchPagesCollector
from steelwatch.collectors.eurlex import EurLexCollector
from steelwatch.collectors.gdelt import GdeltCollector
from steelwatch.collectors.rss import RssCollector


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, text: str):
        self.text = text

    def get(self, *args, **kwargs):
        return FakeResponse(self.text)


def test_eurlex_daily_page_keeps_only_relevant_legal_link():
    fixture = (Path(__file__).parent / "fixtures" / "eurlex_daily.html").read_text(encoding="utf-8")
    config = {
        "keywords": {
            "china": ["china"],
            "materials": ["steel"],
            "global_steel_policy": ["union steel market", "global overcapacity"],
            "exclude": [],
        },
        "settings": {},
    }
    collector = EurLexCollector(
        {"name": "EUR-Lex", "lookback_days": 1, "series": ["L"]}, config
    )
    collector.session = FakeSession(fixture)
    items = collector.collect()
    assert len(items) == 1
    assert items[0].source_kind == "official-law"
    assert items[0].url.endswith("/eli/reg_impl/2026/1457/oj/eng")


class FakeJsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeEcSession:
    def __init__(self, fixture):
        self.fixture = fixture

    def get(self, url, **kwargs):
        if "/groupInitiatives/" in url:
            initiative_id = url.rsplit("/", 1)[-1]
            return FakeJsonResponse(self.fixture["details"][initiative_id])
        return FakeJsonResponse(self.fixture["search"])


def test_ec_have_your_say_collects_steel_and_cbam_with_feedback_deadline():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "ec_have_your_say.json").read_text(
            encoding="utf-8"
        )
    )
    config = {
        "keywords": {
            "china": ["china"],
            "materials": ["steel", "iron"],
            "global_steel_policy": ["steel regulation"],
            "universal_policy": ["carbon border adjustment mechanism", "cbam"],
            "exclude": [],
        },
        "settings": {},
    }
    collector = EcHaveYourSayCollector(
        {
            "name": "EC Have Your Say",
            "lookback_days": 5000,
            "queries": ["steel", "CBAM"],
        },
        config,
    )
    collector.session = FakeEcSession(fixture)

    items = sorted(collector.collect(), key=lambda item: item.title)

    assert len(items) == 2
    cbam, steel = items
    assert cbam.metadata["consultation"]["status"] == "CLOSED"
    assert steel.metadata["consultation"]["status"] == "OPEN"
    assert steel.metadata["consultation"]["closes_at"] == "2026-08-12T23:59:59Z"
    assert steel.url.endswith(
        "/17672-Ecodesign-requirements-for-iron-and-steel-products_en"
    )
    assert steel.source_kind == "official-notice"


class FakeRichResponse:
    def __init__(self, *, text="", content=b"", status_code=200):
        self.text = text
        self.content = content or text.encode("utf-8")
        self.status_code = status_code
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeRichSession:
    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


def test_ec_watch_pages_collects_dated_cbam_document():
    html = """
    <html><body>
      <div class="document-card">
        <h3>State-of-play CBAM accreditation</h3>
        <p>25 September 2026</p>
        <a href="/files/state-of-play-cbam.pdf">Download</a>
      </div>
    </body></html>
    """
    collector = EcWatchPagesCollector(
        {
            "name": "EC Watch",
            "lookback_days": 5000,
            "pages": [
                {
                    "name": "DG TAXUD · CBAM Verification",
                    "url": "https://taxation-customs.ec.europa.eu/cbam-verification_en",
                    "allowed_domains": ["ec.europa.eu"],
                    "match_terms": ["cbam", "accreditation"],
                }
            ],
        },
        {"settings": {}},
    )
    collector.session = FakeRichSession(FakeRichResponse(text=html))

    items = collector.collect()

    assert len(items) == 1
    assert items[0].title == "State-of-play CBAM accreditation"
    assert items[0].published_at.startswith("2026-09-25")
    assert items[0].metadata["scope_relevant"] is True
    assert items[0].source_kind == "official-notice"


def test_rss_collector_keeps_eu_ets_policy_signal():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><item>
      <title>EU ETS surrender and compliance data for steel and CBAM</title>
      <link>https://climate.ec.europa.eu/news/eu-ets-update_en</link>
      <description>Commission update on EU ETS compliance and steel carbon costs.</description>
      <pubDate>Fri, 25 Sep 2026 10:00:00 GMT</pubDate>
      <source url="https://climate.ec.europa.eu/">European Commission</source>
    </item></channel></rss>"""
    config = {
        "settings": {},
        "keywords": {
            "china": [],
            "materials": ["steel"],
            "global_steel_policy": [],
            "universal_policy": ["eu ets", "cbam"],
            "exclude": [],
        },
        "official_domains": {"ec.europa.eu": "欧盟"},
    }
    collector = RssCollector(
        {
            "name": "RSS",
            "lookback_days": 5000,
            "feeds": [{"url": "https://example.com/feed.xml", "region": "欧洲"}],
        },
        config,
    )
    collector.session = FakeRichSession(FakeRichResponse(content=xml))

    items = collector.collect()

    assert len(items) == 1
    assert items[0].source_kind == "official-notice"
    assert items[0].country == "欧盟"
    assert items[0].source_name == "European Commission"


class FakeGdeltResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload or {}
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeGdeltSession:
    def get(self, *args, **kwargs):
        query = kwargs["params"]["query"]
        if query == "rate-limited":
            return FakeGdeltResponse(429)
        return FakeGdeltResponse(
            200,
            {
                "articles": [
                    {
                        "title": "China steel tariff quota update",
                        "url": "https://example.com/china-steel-quota",
                        "domain": "example.com",
                        "sourcecountry": "United Kingdom",
                        "seendate": "20260927T120000Z",
                        "language": "English",
                    }
                ]
            },
        )


def test_gdelt_continues_when_one_query_is_rate_limited():
    config = {
        "settings": {},
        "keywords": {
            "china": ["china"],
            "materials": ["steel"],
            "global_steel_policy": ["steel tariff quota"],
            "universal_policy": [],
            "exclude": [],
        },
        "official_domains": {},
    }
    collector = GdeltCollector(
        {
            "name": "GDELT",
            "lookback_days": 7,
            "max_records_per_query": 20,
            "retries": 1,
            "query_delay_seconds": 0,
            "queries": ["rate-limited", "works"],
        },
        config,
    )
    collector.session = FakeGdeltSession()

    items = collector.collect()

    assert len(items) == 1
    assert items[0].title == "China steel tariff quota update"
