import json

import pytest

from steelwatch.config import load_config
from steelwatch.editorial import (
    add_review_context, apply_translations, has_chinese_title, validate_batch,
)
from steelwatch.pipeline import _apply_editorial, _build_review_queue, _review_counts
from steelwatch.render import _rss


def item(identifier="one", date="2026-11-01", **extra):
    return {"id": identifier, "url": f"https://example.org/{identifier}",
            "published_at": date, "first_seen": date, "last_seen": date,
            "title_original": "Steel trade consultation", "source_excerpt": "Source excerpt",
            "translation_state": "pending", "source": {"kind": "news"}, **extra}


def test_different_review_dates_for_one_url_are_independent():
    first = item(date="2026-11-01")
    second = item(date="2026-11-02")
    reviews = [{"url": first["url"], "published_date": row["published_at"],
                "title_zh": title, "reviewed_at": "2026-11-03"}
               for row, title in [(first, "第一版"), (second, "第二版")]]
    _apply_editorial([first, second], {"editorial": reviews})
    assert [first["title_zh"], second["title_zh"]] == ["第一版", "第二版"]


def test_batch_loading_preserves_history_without_rewriting_large_configs(tmp_path):
    (tmp_path / "sources.json").write_text('{"settings": {}}')
    original = [{"url": "https://example.org/old", "published_date": "2026-10-01"}]
    (tmp_path / "editorial.json").write_text(json.dumps(original))
    (tmp_path / "reviews").mkdir()
    batch = {"schema_version": 1, "translations": [{
        "url": "https://example.org/new", "published_date": "2026-11-01",
        "title_original": "Steel", "title_zh": "钢铁", "translated_at": "2026-11-01",
    }]}
    (tmp_path / "reviews/20261101.json").write_text(json.dumps(batch))
    config = load_config(tmp_path / "sources.json")
    assert config["editorial"] == original
    assert config["translations"][0]["title_zh"] == "钢铁"
    assert json.loads((tmp_path / "editorial.json").read_text()) == original


def test_new_duplicate_requires_a_target():
    with pytest.raises(ValueError, match="duplicate_of"):
        validate_batch({"schema_version": 1, "triage": [{
            "url": "https://example.org/new", "published_date": "2026-11-01",
            "decision": "duplicate", "reason_zh": "同题", "attempted_at": "2026-11-01",
            "coverage": "仅标题分流",
        }]})


def test_title_translation_never_verifies_and_expires_on_source_changes():
    row = item()
    config = {"translations": [{"url": row["url"], "published_date": "2026-11-01",
               "title_original": row["title_original"], "title_zh": "钢铁贸易咨询",
               "translated_at": "2026-11-02"}]}
    apply_translations([row], config)
    assert has_chinese_title(row)
    assert _review_counts([row])["pending_analysis"] == 1
    assert row["translation_state"] == "pending"
    assert _review_counts([row])["pending_translation"] == 0
    row["title_original"] = "A changed source title"
    apply_translations([row], config)
    assert not has_chinese_title(row)
    row["title_original"] = "Steel trade consultation"
    row["published_at"] = "2026-11-03"
    apply_translations([row], config)
    assert not has_chinese_title(row)


def test_existing_chinese_title_does_not_need_retranslation():
    row = item(title_original="中国钢材出口")
    assert has_chinese_title(row)
    assert _review_counts([row])["pending_analysis"] == 1


def test_retry_queue_is_bounded_and_honours_cooldown_and_manual_policy():
    rows = [item(str(n), review_disposition="blocked", review_attempted_at="2026-11-01")
            for n in range(7)]
    rows[5]["retry_policy"] = "manual"
    rows[6]["retry_after"] = "2026-11-20"
    rows[4]["source"]["official"] = True
    queue = add_review_context(_build_review_queue(rows, "2026-11-15"), rows, "2026-11-15")
    assert queue["actionable_count"] == 0 and queue["blocked_count"] == 7
    assert queue["retry_due_count"] == 5 and len(queue["retry_items"]) == 4
    assert queue["retry_items"][0]["id"] == "4"
    assert not {"5", "6"} & {row["id"] for row in queue["retry_items"]}


def test_observation_time_does_not_change_work_fingerprint():
    row = item()
    first = add_review_context(_build_review_queue([row], "2026-11-01"), [row], "2026-11-15")
    row["last_seen"] = "2026-11-15"
    second = add_review_context(_build_review_queue([row], "2026-11-15"), [row], "2026-11-15")
    assert first["work_fingerprint"] == second["work_fingerprint"]
    row["source_excerpt"] = "A new source excerpt"
    third = add_review_context(_build_review_queue([row], "2026-11-15"), [row], "2026-11-15")
    assert first["work_fingerprint"] != third["work_fingerprint"]


def test_rss_translation_does_not_publish_an_unverified_impact():
    row = item(source_translation={"title_zh": "钢铁贸易咨询"}, impact_zh="不应发布的结论")
    feed = _rss([row], "2026-11-15")
    assert "钢铁贸易咨询" in feed and "不应发布的结论" not in feed


def test_translate_preserves_collection_and_review_timestamps(tmp_path, monkeypatch):
    from steelwatch import pipeline
    data = tmp_path / "data"
    data.mkdir()
    (data / "items.json").write_text(json.dumps({"generated_at": "2026-11-01", "items": [item()]}))
    (data / "status.json").write_text(json.dumps({"generated_at": "2026-11-01",
                                                "editorial_updated_at": "2026-11-02"}))

    def translate(items, settings, previous):
        items[0]["machine_translation"] = {"title_zh": "钢铁贸易咨询"}
        return {"status": "available", "translated": 1, "warnings": []}

    monkeypatch.setattr(pipeline, "translate_pending", translate)
    monkeypatch.setattr(pipeline, "_collect", lambda _: pytest.fail("no collection allowed"))
    pipeline.translate_existing({}, data, tmp_path / "docs")
    status = json.loads((data / "status.json").read_text())
    assert status["generated_at"] == "2026-11-01"
    assert status["editorial_updated_at"] == "2026-11-02"
    assert status["pending_analysis"] == 1 and status["pending_translation"] == 0
    assert status["machine_translated_items"] == 1


def test_version_changes_preserve_reviewed_history_and_unchanged_pending_cache(tmp_path, monkeypatch):
    from steelwatch import pipeline
    from steelwatch.models import RawItem, SourceResult
    from test_pipeline import FakeEnricher

    old = item(translation_state="complete", review_method="source_checked")
    pending = item("pending", title_original="Chinese steel exports",
                   machine_translation={"title_zh": "已缓存译文"})
    data = tmp_path / "data"
    data.mkdir()
    (data / "items.json").write_text(json.dumps({"items": [old, pending]}))
    raws = [RawItem(id=row["id"], url=row["url"], title=row["title_original"],
                   published_at=date, source_id="test", source_name="Test", source_kind="news",
                   country="中国", region="亚洲", excerpt=row["source_excerpt"],
                   metadata={"scope_relevant": True})
            for row, date in [(old, "2026-11-15"), (pending, "2026-11-01")]]
    monkeypatch.setattr(pipeline, "_collect", lambda _: [SourceResult("test", "Test", True, raws)])
    monkeypatch.setattr(pipeline, "GitHubModelsEnricher", FakeEnricher)
    monkeypatch.setattr(pipeline, "_hydrate_excerpts", lambda *args: [])
    pipeline.run_update({"settings": {"retention_days": 730}}, data, tmp_path / "docs")
    saved = json.loads((data / "items.json").read_text())["items"]
    historical = [row for row in saved if row["url"] == old["url"]]
    assert len(historical) == 2
    assert any(row["review_method"] == "source_checked" for row in historical if "review_method" in row)
    cached = next(row for row in saved if row["id"] == "pending")
    assert cached["machine_translation"]["title_zh"] == "已缓存译文"


def test_missing_referenced_old_review_is_restored_without_reviewing_new_edition():
    from steelwatch.pipeline import _apply_triage
    current = item(date="2026-11-03")
    duplicate = item("copy", date="2026-11-02")
    config = {"editorial": [{"url": current["url"], "published_date": "2026-11-01",
        "title_zh": "旧版已核验", "title_en": "Verified old edition", "reviewed_at": "2026-11-02",
        "evidence_url": "https://example.org/evidence", "coverage": "Read the older edition"}],
        "triage": [{"url": duplicate["url"], "published_date": "2026-11-02",
                    "decision": "duplicate", "duplicate_of": current["url"]}]}
    rows = [current, duplicate]
    _apply_editorial(rows, config)
    _apply_triage(rows, config)
    assert len(rows) == 3
    assert "review_method" not in current
    assert duplicate["review_disposition"] == "duplicate"
    restored = rows[-1]
    assert restored["review_method"] == "source_checked" and not restored["source_excerpt"]
    assert restored["published_at"].startswith("2026-11-01")
    _apply_editorial(rows, config)
    assert len(rows) == 3


def test_corrected_date_remembers_original_source_revision():
    row = item(date="2026-11-12")
    config = {"editorial": [{"url": row["url"], "match_published_date": "2026-11-12",
                            "published_date": "2026-11-13", "reviewed_at": "2026-11-15"}]}
    _apply_editorial([row], config)
    assert row["source_published_date"] == "2026-11-12"
    assert row["published_at"].startswith("2026-11-13")
