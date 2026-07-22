from pathlib import Path

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
