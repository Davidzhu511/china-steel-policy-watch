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
                    "title_en": "Investigation into Chinese hot-rolled steel",
                    "summary_zh": "主管机关启动调查。",
                    "summary_en": "The authority opened an investigation.",
                    "impact_zh": "出口商应核对涉案范围。",
                    "impact_en": "Exporters should verify the product scope.",
                    "category": "贸易救济",
                    "status": "调查中",
                    "importance": "高",
                    "country": "测试国",
                    "region": "亚洲",
                    "products": ["热轧钢"],
                    "products_en": ["hot-rolled steel"],
                    "tags": ["反倾销"],
                    "tags_en": ["anti-dumping"],
                    "confidence": 0.9,
                    "translation_state": "complete",
                }
                for item in items
            ],
            [],
        )

    def backfill_english(self, items):
        return (
            {
                item["id"]: {
                    "title_en": "Existing policy title",
                    "summary_en": "Existing English summary.",
                    "impact_en": "Existing English impact.",
                    "products_en": ["steel"],
                    "tags_en": ["policy"],
                }
                for item in items
            },
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
    assert payload["items"][0]["title_en"] == "Investigation into Chinese hot-rolled steel"
    assert payload["items"][0]["summary_en"] == "The authority opened an investigation."
    assert (docs / "data" / "items.json").exists()


def test_update_pipeline_backfills_english_for_existing_history(tmp_path, monkeypatch):
    data, docs = tmp_path / "data", tmp_path / "docs"
    data.mkdir()
    existing = {
        "id": "existing-1",
        "title_zh": "既有政策",
        "title_original": "Existing policy",
        "summary_zh": "既有摘要。",
        "impact_zh": "既有影响。",
        "url": "https://example.com/existing",
        "published_at": "2026-07-21T00:00:00Z",
        "source": {"id": "test", "name": "Test", "kind": "official-notice", "official": True},
        "country": "测试国",
        "region": "亚洲",
        "category": "产业政策",
        "status": "已生效",
        "importance": "中",
        "products": ["钢铁"],
        "tags": ["政策"],
        "translation_state": "complete",
        "first_seen": "2026-07-21T00:00:00Z",
        "last_seen": "2026-07-21T00:00:00Z",
    }
    (data / "items.json").write_text(
        json.dumps({"generated_at": "2026-07-21T00:00:00Z", "items": [existing]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(pipeline, "_collect", lambda config: [])
    monkeypatch.setattr(pipeline, "_hydrate_excerpts", lambda items, settings: [])
    monkeypatch.setattr(pipeline, "GitHubModelsEnricher", FakeEnricher)
    config = {
        "settings": {"retention_days": 730, "english_backfill_per_run": 24},
        "keywords": {"china": [], "materials": [], "global_steel_policy": [], "exclude": []},
        "sources": {},
    }
    pipeline.run_update(config, data, docs)
    payload = json.loads((data / "items.json").read_text(encoding="utf-8"))
    assert payload["items"][0]["title_en"] == "Existing policy title"
    assert payload["items"][0]["summary_en"] == "Existing English summary."
    assert payload["items"][0]["products_en"] == ["steel"]
