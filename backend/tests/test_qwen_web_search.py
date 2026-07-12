from keeplix.providers.qwen_web_search import _append_delta, _extract_sources


def test_stream_delta_merge_and_source_extraction():
    parts: list[str] = []
    _append_delta(parts, "第一段")
    _append_delta(parts, "第一段第二段")
    assert "".join(parts) == "第一段第二段"

    sources = _extract_sources(
        [{"output": {"references": [{"url": "https://example.com/a", "title": "证据"}]}}],
        "参考 https://example.org/b 。",
    )
    assert {(source.url, source.title) for source in sources} == {
        ("https://example.com/a", "证据"),
        ("https://example.org/b", None),
    }
