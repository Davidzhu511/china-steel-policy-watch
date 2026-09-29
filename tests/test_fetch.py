from steelwatch import fetch


class FakeResponse:
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, html):
        self.text = html
        self.content = html.encode()


def test_page_excerpt_strips_html_from_metadata(monkeypatch):
    page = FakeResponse(
        '<html><head><meta name="description" content="Steel quota details: '
        '&lt;div&gt;&lt;p&gt;The new rules cover imports of steel.&lt;/p&gt;&lt;/div&gt;"'
        '></head></html>'
    )
    monkeypatch.setattr(fetch, "safe_get", lambda session, url, timeout: page)
    excerpt = fetch.fetch_page_excerpt("https://example.com/steel", official=True)
    assert "The new rules cover imports of steel." in excerpt
    assert "<div>" not in excerpt


def test_page_excerpt_rejects_access_challenge(monkeypatch):
    page = FakeResponse(
        "<html><body>Your request has been flagged as potentially automated. "
        "Please complete the CAPTCHA.</body></html>"
    )
    monkeypatch.setattr(fetch, "safe_get", lambda session, url, timeout: page)
    assert fetch.fetch_page_excerpt("https://example.com/steel", official=True) == ""
