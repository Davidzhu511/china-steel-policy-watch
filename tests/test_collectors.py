import json
from pathlib import Path

from steelwatch.collectors.ec_have_your_say import EcHaveYourSayCollector
from steelwatch.collectors.eurlex import EurLexCollector


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
