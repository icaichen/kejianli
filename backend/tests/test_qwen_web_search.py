from keeplix.providers.qwen_web_search import _append_delta, _extract_sources, _is_content_url


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


def test_source_extraction_rejects_image_assets_and_thumbnail_urls():
    image_urls = [
        "https://example.com/img/source.png",
        "https://images.example.com/asset?id=1&f=JPEG?w=200&h=200",
        "https://images.example.com/asset?id=2&format=webp",
        "https://spark",
    ]
    sources = _extract_sources(
        [
            {
                "output": {
                    "references": [
                        {"url": "https://example.com/article", "title": "正文"},
                        *({"url": url, "title": "缩略图"} for url in image_urls),
                    ]
                }
            }
        ],
        " ".join(image_urls),
    )

    assert [source.url for source in sources] == ["https://example.com/article"]
    assert all(not _is_content_url(url) for url in image_urls)
