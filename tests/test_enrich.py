from steelwatch.enrich import _validate
from steelwatch.models import RawItem


def test_news_status_cannot_be_mislabelled_as_law():
    raw = RawItem(
        id="x",
        title="China steel news",
        url="https://example.com/x",
        published_at="2026-07-21T00:00:00Z",
        source_id="news",
        source_name="News",
        source_kind="news",
    )
    result = _validate(
        {
            "status": "已生效",
            "category": "市场与产能",
            "importance": "中",
            "title_zh": "中国钢铁新闻",
            "summary_zh": "摘要",
            "impact_zh": "影响",
        },
        raw,
    )
    assert result["status"] == "新闻"
    assert result["translation_state"] == "complete"
    assert result["title_en"] == raw.title
    assert result["summary_en"]
    assert result["impact_en"]
