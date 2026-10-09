import json

from steelwatch.pipeline import _apply_triage, _review_counts
from steelwatch.render import render_outputs


def test_exact_version_triage_clears_stale_decisions_and_preserves_links():
    target = {"url": "https://example.org/main", "published_at": "2026-10-05",
              "review_method": "source_checked", "translation_state": "complete"}
    duplicate = {"url": "https://example.org/copy", "published_at": "2026-10-06",
                 "source": {"name": "Publisher"}}
    config = {"triage": [{"url": duplicate["url"], "published_date": "2026-10-06",
                          "decision": "duplicate", "duplicate_of": target["url"]}]}
    _apply_triage([target, duplicate], config)
    assert duplicate["review_disposition"] == "duplicate"
    assert target["related_sources"] == [{"name": "Publisher", "url": duplicate["url"]}]
    assert _review_counts([target, duplicate])["pending_analysis"] == 0
    duplicate["published_at"] = "2026-10-07"
    _apply_triage([target, duplicate], config)
    assert "review_disposition" not in duplicate
    assert "duplicate_of" not in duplicate
    assert _review_counts([target, duplicate])["pending_analysis"] == 1


def test_missing_or_unverified_duplicate_target_remains_pending():
    item = {"url": "https://example.org/copy", "published_at": "2026-10-06"}
    _apply_triage([item], {"triage": [{"url": item["url"], "published_date": "2026-10-06",
                                      "decision": "duplicate", "duplicate_of": "https://example.org/missing"}]})
    assert item["review_disposition"] == "blocked"
    assert _review_counts([item])["pending_analysis"] == 1


def test_translation_complete_is_not_source_verified():
    rows = [{"translation_state": "complete"}, {"review_disposition": "blocked"},
            {"review_disposition": "excluded"}]
    assert _review_counts(rows) == {"active_items": 2, "archived_items": 1,
                                  "verified_items": 0, "pending_analysis": 2,
                                  "pending_translation": 1, "blocked_items": 1}


def test_archived_rows_remain_in_history_but_leave_latest_and_rss(tmp_path):
    data = tmp_path / "data"
    docs = tmp_path / "docs"
    data.mkdir()
    rows = [{"id": str(n), "url": f"https://example.org/{n}",
             "title_original": f"Story {n}", "published_at": "2026-10-06T00:00:00Z",
             "review_disposition": decision}
            for n, decision in enumerate(["blocked", "excluded", "duplicate"])]
    (data / "items.json").write_text(json.dumps({"items": rows, "generated_at": "2026-10-09T00:00:00Z"}))
    (data / "status.json").write_text('{}')
    render_outputs(data, docs)
    assert len(json.loads((docs / "data/items.json").read_text())["items"]) == 3
    assert len(json.loads((docs / "data/latest.json").read_text())["items"]) == 1
    feed = (docs / "feed.xml").read_text()
    assert "Story 0" in feed and "Story 1" not in feed and "Story 2" not in feed
