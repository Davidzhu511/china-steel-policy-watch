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


def test_page_excerpt_rejects_eurlex_robot_notice(monkeypatch):
    page = FakeResponse(
        "<html><h1>JavaScript is disabled</h1><p>In order to continue, we need to "
        "verify that you're not a robot. This requires JavaScript.</p></html>"
    )
    monkeypatch.setattr(fetch, "safe_get", lambda session, url, timeout: page)
    assert fetch.fetch_page_excerpt("https://eur-lex.europa.eu/legal-content/EN/TXT/", official=True) == ""


def test_official_observation_tracks_body_and_same_url_attachment(monkeypatch):
    from contextlib import contextmanager

    source = "https://example.com/steel"
    doc_url = "https://example.com/annex.pdf"
    content = {
        source: b'<main><p>Steel duty 12%.</p><a href="/annex.pdf">Annex</a></main>',
        doc_url: b'%PDF-1.7 annex version A',
    }

    class Response(FakeResponse):
        def __init__(self, url):
            self.url = url
            self.headers = {"Content-Type": "text/html" if url == source else "application/pdf"}

        def iter_content(self, chunk_size):
            yield content[self.url]

    @contextmanager
    def get(session, url, timeout, *, stream):
        assert stream
        yield Response(url)

    monkeypatch.setattr(fetch, "safe_get", get)
    original = fetch.fetch_official_observations(source, timeout=12)
    content[doc_url] = b'%PDF-1.7 annex version B'
    corrected_annex = fetch.fetch_official_observations(source, timeout=12)
    assert corrected_annex["document"] == original["document"]
    assert corrected_annex["attachment:" + doc_url] != original["attachment:" + doc_url]
    content[source] = content[source].replace(b'12%', b'15%')
    amended_notice = fetch.fetch_official_observations(source, timeout=12)
    assert amended_notice["document"] != original["document"]
