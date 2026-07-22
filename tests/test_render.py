import json

from steelwatch.render import render_outputs


def test_render_creates_dashboard_json_and_rss(tmp_path):
    data = tmp_path / "data"
    docs = tmp_path / "docs"
    data.mkdir()
    (data / "items.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-21T00:00:00Z",
                "items": [
                    {
                        "id": "1",
                        "title_zh": "测试法规",
                        "url": "https://example.com/law",
                        "summary_zh": "摘要",
                        "impact_zh": "影响",
                        "published_at": "2026-07-21T00:00:00Z",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (data / "status.json").write_text("{}", encoding="utf-8")
    render_outputs(data, docs)
    assert (docs / "data" / "items.json").exists()
    assert "测试法规" in (docs / "feed.xml").read_text(encoding="utf-8")
    assert (docs / ".nojekyll").exists()
