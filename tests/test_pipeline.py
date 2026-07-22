import json

from steelwatch import pipeline
from steelwatch.models import RawItem, SourceResult


class FakeEnricher:
    model = "test-model"
    available = True

    def __init__(self, settings):
        pass

    def enrich(self, items):
        return (
            [
                {
                    "id": item.id,
                    "relevant": True,
                    "title_zh": "中国热轧钢调查",
                    "summary_zh": "主管机关启动调查。",
                    "impact_zh": "出口商应核对涉案范围。",
                    "category": "贸易救济",
                    "status": "调查中",
                    "importance": "高",
                    "country": "测试国",
                    "region": "亚洲",
                    "products": ["热轧钢"],
                    "tags": ["反倾销"],
                    "confidence": 0.9,
                    "translation_state": "complete",
                }
                for item in items
            ],
            [],
        )


def test_update_pipeline_adds_enriched_item_without_network(tmp_path, monkeypatch):
    raw = RawItem(
        id="item-1",
        title="Anti-dumping investigation into hot-rolled steel from China",
        url="https://example.com/item-1",
        published_at="2026-07-21T00:00:00Z",
        source_id="test",
        source_name="Test authority",
        source_kind="official-notice",
        region="亚洲",
        country="测试国",
        excerpt="The authority opened an investigation into hot-rolled steel from China.",
        metadata={"official": True},
    )
    monkeypatch.setattr(
        pipeline,
        "_collect",
        lambda config: [SourceResult("test", "Test authority", True, [raw])],
    )
    monkeypatch.setattr(pipeline, "_hydrate_excerpts", lambda items, settings: [])
    monkeypatch.setattr(pipeline, "GitHubModelsEnricher", FakeEnricher)
    config = {
        "settings": {"retention_days": 730, "max_new_items_per_run": 10},
        "keywords": {
            "china": ["china"],
            "materials": ["steel", "hot-rolled"],
            "global_steel_policy": [],
            "exclude": [],
        },
        "sources": {},
    }
    data, docs = tmp_path / "data", tmp_path / "docs"
    status = pipeline.run_update(config, data, docs)
    payload = json.loads((data / "items.json").read_text(encoding="utf-8"))
    assert status["new_items"] == 1
    assert payload["items"][0]["title_zh"] == "中国热轧钢调查"
    assert (docs / "data" / "items.json").exists()
