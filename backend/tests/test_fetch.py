"""fetch()：浏览器开关 + 优雅降级（Playwright 缺失/失败都不崩）。"""

from __future__ import annotations

import pytest

from keeplix.core.config import get_settings
from keeplix.engines import analysis


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_fetch_defaults_to_httpx(monkeypatch):
    """默认不开浏览器时不调 Playwright。"""
    called = {"pw": False}

    async def _fake_pw(url, timeout, user_agent):
        called["pw"] = True
        return "<html></html>"

    async def _fake_httpx_get(self, url, headers=None):  # noqa: ARG001
        class R:
            status_code = 200
            text = "<html><title>ok</title></html>"

        return R()

    monkeypatch.setattr(analysis, "_fetch_playwright", _fake_pw)
    monkeypatch.setattr("httpx.AsyncClient.get", _fake_httpx_get)

    result = await analysis.fetch("https://example.com")
    assert called["pw"] is False
    assert result.ok
    assert "<title>ok</title>" in result.html


async def test_fetch_use_browser_calls_playwright(monkeypatch):
    """显式打开浏览器时优先走 Playwright。"""
    called = {"pw": False}

    async def _fake_pw(url, timeout, user_agent):
        called["pw"] = True
        assert user_agent  # 传了 UA 下去
        return "<html>ssr</html>"

    monkeypatch.setattr(analysis, "_fetch_playwright", _fake_pw)
    result = await analysis.fetch("https://example.com", use_browser=True)
    assert called["pw"] is True
    assert result.html == "<html>ssr</html>"
    assert result.status == 200


async def test_fetch_falls_back_when_playwright_missing(monkeypatch):
    """Playwright 抛异常时降级 httpx，不冒泡到调用方。"""

    async def _boom(url, timeout, user_agent):
        raise ImportError("no playwright")

    async def _fake_httpx_get(self, url, headers=None):  # noqa: ARG001
        class R:
            status_code = 200
            text = "<html>httpx</html>"

        return R()

    monkeypatch.setattr(analysis, "_fetch_playwright", _boom)
    monkeypatch.setattr("httpx.AsyncClient.get", _fake_httpx_get)

    result = await analysis.fetch("https://example.com", use_browser=True)
    assert result.status == 200
    assert result.html == "<html>httpx</html>"


async def test_fetch_returns_empty_on_total_failure(monkeypatch):
    """两条链路都失败时给出 status=0 空结果，不抛 500。"""

    async def _fake_httpx_get(self, url, headers=None):  # noqa: ARG001
        raise RuntimeError("no network")

    monkeypatch.setattr("httpx.AsyncClient.get", _fake_httpx_get)

    result = await analysis.fetch("https://example.com")
    assert result.status == 0
    assert result.html == ""
    assert result.ok is False
