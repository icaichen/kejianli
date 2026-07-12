from keeplix.providers.baidu_search import _extract_sources, _request_id


def test_baidu_source_extraction_keeps_valid_unique_web_references():
    sources = _extract_sources(
        [
            {"url": "https://example.com/a", "title": "来源 A", "type": "web"},
            {"url": "https://example.com/a", "title": "重复来源", "type": "web"},
            {"url": "https://example.org/b", "type": "web"},
            {"url": "not-a-url", "title": "无效"},
            None,
        ]
    )

    assert [(source.url, source.title) for source in sources] == [
        ("https://example.com/a", "来源 A"),
        ("https://example.org/b", None),
    ]


def test_baidu_request_id_supports_current_and_legacy_fields():
    assert _request_id({"request_id": "current"}) == "current"
    assert _request_id({"requestId": "camel"}) == "camel"
    assert _request_id({"request_Id": "legacy"}) == "legacy"
    assert _request_id({}) is None
