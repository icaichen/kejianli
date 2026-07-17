"""网站识别入口：只返回可追溯建议，不猜测竞品。"""

from __future__ import annotations

from keeplix.engines.analysis import FetchResult


def test_site_profile_extracts_only_page_backed_suggestions(client, monkeypatch):
    html = """
    <html lang="zh-CN"><head>
      <title>Example Cloud — 企业协作平台</title>
      <meta property="og:site_name" content="Example Cloud" />
      <meta name="description" content="为团队提供可审计的协作与工作流。" />
      <script type="application/ld+json">
      {"@type":"Service","name":"企业协作服务","serviceType":"企业协作软件"}
      </script>
    </head><body><h1>Example Cloud</h1></body></html>
    """

    async def allow_public_host(_url: str) -> None:
        return None

    async def fake_fetch(url: str):
        return FetchResult(
            url="https://www.example.com/",
            status=200,
            html=html,
        )

    monkeypatch.setattr(
        "keeplix.services.site_profile_service._assert_public_host",
        allow_public_host,
    )
    monkeypatch.setattr(
        "keeplix.services.site_profile_service._fetch_public_site",
        fake_fetch,
    )
    response = client.post(
        "/api/projects/discover",
        json={"url": "example.com"},
    )
    assert response.status_code == 200
    profile = response.json()
    assert profile["url"] == "https://www.example.com/"
    assert profile["brand_name"] == "Example Cloud"
    assert profile["category"] == "企业协作软件"
    assert profile["summary"] == "为团队提供可审计的协作与工作流。"
    assert profile["language"] == "zh-CN"
    assert {item["field"] for item in profile["evidence"]} == {
        "brand_name",
        "category",
        "summary",
        "language",
    }
    assert profile["warnings"] == [
        "竞争对手不能仅从自有官网可靠判定，需要你确认。"
    ]


def test_site_profile_rejects_private_targets(client):
    response = client.post(
        "/api/projects/discover",
        json={"url": "http://127.0.0.1:8000/health"},
    )
    assert response.status_code == 400
    assert "本机或内网" in response.json()["detail"]


def test_site_profile_explains_fetch_failure(client, monkeypatch):
    async def allow_public_host(_url: str) -> None:
        return None

    async def fake_fetch(url: str):
        return FetchResult(url=url, status=403, html="")

    monkeypatch.setattr(
        "keeplix.services.site_profile_service._assert_public_host",
        allow_public_host,
    )
    monkeypatch.setattr(
        "keeplix.services.site_profile_service._fetch_public_site",
        fake_fetch,
    )
    response = client.post(
        "/api/projects/discover",
        json={"url": "https://blocked.example"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "网站返回 HTTP 403，无法读取首页"


def test_site_profile_rejects_redirect_to_private_target(monkeypatch):
    import httpx
    import pytest

    from keeplix.services import site_profile_service

    checked: list[str] = []

    async def assert_public(url: str) -> None:
        checked.append(url)
        if "127.0.0.1" in url:
            raise ValueError("只能读取公开网站，不支持本机或内网地址")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    class FakeClient(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(site_profile_service, "_assert_public_host", assert_public)
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    with pytest.raises(ValueError, match="本机或内网"):
        import asyncio

        asyncio.run(site_profile_service._fetch_public_site("https://public.example/"))
    assert checked == ["https://public.example/", "http://127.0.0.1/admin"]
