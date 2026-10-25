from nexus.catalog import parse_markdown, is_public_http_url

def test_markdown_parsing_and_dedup():
    doc = "# APIs\n## Weather\n- [Forecast](https://example.com/api) - Weather data\n- [Forecast](https://example.com/api)\n## News\n- [Headlines](https://news.example.org)"
    items = parse_markdown(doc)
    assert len(items) == 2
    assert items[0]["category"] == "Weather"
    assert items[1]["category"] == "News"

def test_rejects_local_urls():
    for url in ("http://localhost", "http://127.0.0.1", "http://192.168.1.2", "file:///etc/passwd", "http://169.254.169.254"):
        assert not is_public_http_url(url)
