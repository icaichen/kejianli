from keeplix.providers.kimi_web_search import _extract_sources


def test_kimi_source_extraction_from_structured_and_inline_urls():
    sources = _extract_sources(
        [{"search": {"results": [{"url": "https://example.com/a", "title": "来源 A"}]}}],
        "另见 https://example.org/b 。",
    )
    assert {(source.url, source.title) for source in sources} == {
        ("https://example.com/a", "来源 A"),
        ("https://example.org/b", None),
    }
