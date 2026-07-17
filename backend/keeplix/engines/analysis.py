"""抓取 + HTML 结构解析 → signals（供 scoring 的 checks 消费）。

抓取：默认 httpx（快 + 零依赖）。开 `KEEPLIX_USE_BROWSER=1` 且装了 Playwright
（`uv sync --extra browser` + `playwright install chromium`）后走浏览器抓 SSR 页。
解析：BeautifulSoup 抽取结构/权威/新鲜度/实体信号，输出 dict signals。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

from keeplix.core.config import get_settings
from keeplix.core.logging import get_logger

log = get_logger("engines.analysis")

_YEAR_RE = re.compile(r"20\d{2}")
_NUM_RE = re.compile(r"\d")
_PCT_RE = re.compile(r"\d+\s*[%％]")


@dataclass
class FetchResult:
    url: str
    status: int
    html: str
    ok: bool = field(init=False)

    def __post_init__(self) -> None:
        self.ok = self.status == 200 and bool(self.html)


async def fetch(url: str, timeout: float = 20.0, use_browser: bool | None = None) -> FetchResult:
    """抓取页面 HTML。默认 httpx；`use_browser` 或 `KEEPLIX_USE_BROWSER=1` 时用 Playwright。

    任何失败（无网络、DNS、超时、被墙、Playwright 缺失）都降级为 status=0 的空结果，
    保证骨架在任何机器上都不抛 500——抓取失败的页面自然得低分。
    """
    settings = get_settings()
    should_use_browser = settings.use_browser if use_browser is None else use_browser
    user_agent = settings.fetch_user_agent

    if should_use_browser:
        try:
            html = await _fetch_playwright(url, timeout, user_agent)
            if html is not None:
                return FetchResult(url=url, status=200, html=html)
        except Exception as e:  # noqa: BLE001 - Playwright 缺失/失败都降级 httpx
            log.info("Playwright 抓取失败，降级 httpx：%s", e)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": user_agent})
            final_url = str(getattr(resp, "url", url))
            return FetchResult(url=final_url, status=resp.status_code, html=resp.text)
    except Exception as e:  # noqa: BLE001 - 网络/沙箱无网都降级，不抛 500
        log.warning("抓取失败（%s），降级为空结果：%s", url, e)
        return FetchResult(url=url, status=0, html="")


async def _fetch_playwright(url: str, timeout: float, user_agent: str) -> str | None:
    """仅当安装了 playwright extras 时生效；否则抛 ImportError 由上层降级。

    等到 networkidle 以确保 SSR/CSR 页面的初始异步请求都完成——GEO 分析常需要
    看动态注入的 JSON-LD、作者卡片等，httpx 拿不到。
    """
    from playwright.async_api import async_playwright  # type: ignore

    timeout_ms = timeout * 1000
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1440, "height": 900},
            )
            page = await context.new_page()
            await page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            return await page.content()
        finally:
            await browser.close()


def parse(fetch_result: FetchResult, preferred_sources: list[str] | None = None) -> dict:
    """把 HTML 解析成 scoring 需要的 signals。"""
    preferred_sources = preferred_sources or []
    soup = BeautifulSoup(fetch_result.html or "", "html.parser")

    text = soup.get_text(" ", strip=True)
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    headings = {f"h{i}": len(soup.find_all(f"h{i}")) for i in range(1, 5)}
    links = [str(a.get("href", "")) for a in soup.find_all("a", href=True)]
    external_links = [h for h in links if h.startswith("http")]

    first_para = paragraphs[0] if paragraphs else ""
    avg_para_len = (sum(len(p) for p in paragraphs) / len(paragraphs)) if paragraphs else 0

    has_author = bool(
        soup.find(attrs={"name": "author"})
        or soup.find(attrs={"rel": "author"})
        or soup.find(class_=re.compile(r"author|byline", re.I))
    )
    has_date = bool(
        soup.find("time")
        or soup.find(attrs={"name": re.compile(r"date|publish", re.I)})
        or soup.find(attrs={"property": re.compile(r"published_time", re.I)})
    )
    has_jsonld = bool(soup.find_all("script", attrs={"type": "application/ld+json"}))
    site_name = soup.find(attrs={"property": "og:site_name"})

    preferred_hits = [h for h in external_links if any(src in h for src in preferred_sources)]

    return {
        # 原始度量（供 checks 计算）
        "status": fetch_result.status,
        "text_length": len(text),
        "title": (soup.title.string or "").strip() if soup.title else "",
        "first_paragraph": first_para,
        "avg_paragraph_length": avg_para_len,
        "headings": headings,
        "list_count": len(soup.find_all(["ul", "ol"])),
        "external_link_count": len(external_links),
        "has_author": has_author,
        "has_date": has_date,
        "has_recent_year": bool(_YEAR_RE.search(text)),
        "has_numbers": bool(_NUM_RE.search(text)),
        "has_percentages": bool(_PCT_RE.search(text)),
        "has_jsonld": has_jsonld,
        "has_site_name": bool(site_name),
        "preferred_source_hits": len(preferred_hits),
        "text_snapshot": text[:2000],
    }
