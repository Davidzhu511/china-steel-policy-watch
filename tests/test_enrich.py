from steelwatch.enrich import GitHubModelsEnricher, _parse_json_object, _validate
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



class FakeModelResponse:
    def __init__(self, content, *, status_code=200, finish_reason="stop"):
        self.status_code = status_code
        self._content = content
        self._finish_reason = finish_reason

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return {
            "choices": [
                {
                    "finish_reason": self._finish_reason,
                    "message": {"content": self._content},
                }
            ]
        }


class FakeModelSession:
    def __init__(self):
        self.models = []

    def post(self, *args, **kwargs):
        model = kwargs["json"]["model"]
        self.models.append(model)
        if model == "openai/gpt-4.1-mini":
            return FakeModelResponse("")
        return FakeModelResponse('{"items": []}')


def test_model_request_falls_back_when_primary_returns_empty_content(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    enricher = GitHubModelsEnricher(
        {
            "model": "openai/gpt-4.1-mini",
            "model_fallbacks": ["openai/gpt-4o-mini"],
        }
    )
    session = FakeModelSession()
    enricher.session = session

    parsed = enricher._request(
        {
            "model": enricher.model,
            "messages": [{"role": "user", "content": "test"}],
        }
    )

    assert parsed == {"items": []}
    assert session.models == ["openai/gpt-4.1-mini", "openai/gpt-4o-mini"]



def test_parse_json_object_accepts_markdown_and_leading_text():
    assert _parse_json_object('Here is the result:\n{"items": []}') == {"items": []}
    assert _parse_json_object('```json\n{"items": []}\n```') == {"items": []}
    assert _parse_json_object('\ufeff  {"items": []}') == {"items": []}
