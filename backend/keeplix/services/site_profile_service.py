"""从公开官网提取可复查的项目设置建议，不直接写入项目。"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
from typing import Any, Literal, cast
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from keeplix.core.config import get_settings
from keeplix.engines import analysis
from keeplix.schemas import SiteProfileEvidence, SiteProfileRequest, SiteProfileResponse

_TITLE_SPLIT_RE = re.compile(r"\s+(?:[-|\u2014\u2013\uff5c])\s+")
_BRAND_TYPES = {
    "Organization",
    "Corporation",
    "LocalBusiness",
    "Brand",
    "Product",
    "SoftwareApplication",
    "WebSite",
}
_CATEGORY_KEYS = ("serviceType", "category", "applicationCategory")


def _normalize_url(value: str) -> str:
    candidate = value.strip()
    if not re.match(r"^https?://", candidate, re.I):
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("请输入有效的 HTTP(S) 网站地址")
    if parsed.username or parsed.password:
        raise ValueError("网站地址不能包含账号凭据")
    hostname = parsed.hostname.encode("idna").decode("ascii")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("请输入有效的 HTTP(S) 网站地址") from error
    netloc = hostname if port is None else f"{hostname}:{port}"
    return urlunparse((parsed.scheme.lower(), netloc, parsed.path or "/", "", parsed.query, ""))


async def _assert_public_host(url: str) -> None:
    hostname = urlparse(url).hostname or ""
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise ValueError("只能读取公开网站，不支持本机或内网地址")
    try:
        literal = ipaddress.ip_address(hostname)
        addresses = [literal]
    except ValueError:
        try:
            records = await asyncio.to_thread(
                socket.getaddrinfo,
                hostname,
                None,
                0,
                socket.SOCK_STREAM,
            )
        except socket.gaierror as error:
            raise ValueError("网站域名无法解析") from error
        addresses = list({ipaddress.ip_address(record[4][0]) for record in records})
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("只能读取公开网站，不支持本机或内网地址")


async def _fetch_public_site(url: str, *, max_redirects: int = 5) -> analysis.FetchResult:
    """逐次校验重定向目标，避免公开网址把服务端带入内网。"""
    settings = get_settings()
    current = url
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        for _ in range(max_redirects + 1):
            await _assert_public_host(current)
            try:
                response = await client.get(
                    current,
                    headers={"User-Agent": settings.fetch_user_agent},
                )
            except httpx.HTTPError:
                return analysis.FetchResult(url=current, status=0, html="")
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    return analysis.FetchResult(
                        url=str(response.url),
                        status=response.status_code,
                        html=response.text,
                    )
                current = _normalize_url(urljoin(str(response.url), location))
                continue
            return analysis.FetchResult(
                url=str(response.url),
                status=response.status_code,
                html=response.text,
            )
    raise ValueError("网站重定向次数过多，无法读取首页")


def _meta(soup: BeautifulSoup, *selectors: tuple[str, str]) -> tuple[str, str]:
    for attribute, value in selectors:
        element = soup.find("meta", attrs={attribute: value})
        content = str(element.get("content", "")).strip() if element else ""
        if content:
            return content, f"meta[{attribute}={value}]"
    return "", ""


def _jsonld_nodes(soup: BeautifulSoup) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or script.get_text() or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                nodes.extend(item for item in graph if isinstance(item, dict))
            nodes.append(candidate)
    return nodes


def _node_types(node: dict[str, Any]) -> set[str]:
    raw = node.get("@type", "")
    return {str(item) for item in raw} if isinstance(raw, list) else {str(raw)}


def _first_text(nodes: list[dict[str, Any]], keys: tuple[str, ...]) -> tuple[str, str]:
    for node in nodes:
        for key in keys:
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip(), f"JSON-LD {key}"
            if isinstance(value, list):
                text = next((str(item).strip() for item in value if str(item).strip()), "")
                if text:
                    return text, f"JSON-LD {key}"
    return "", ""


def _extract_profile(fetch_result: analysis.FetchResult) -> SiteProfileResponse:
    soup = BeautifulSoup(fetch_result.html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    nodes = _jsonld_nodes(soup)
    brand_nodes = [node for node in nodes if _node_types(node) & _BRAND_TYPES]

    brand_name, brand_source = _meta(
        soup,
        ("property", "og:site_name"),
        ("name", "application-name"),
    )
    if not brand_name:
        brand_name, brand_source = _first_text(brand_nodes, ("name", "legalName"))
    if not brand_name and title:
        brand_name = _TITLE_SPLIT_RE.split(title, maxsplit=1)[0].strip()
        brand_source = "title"

    category, category_source = _first_text(nodes, _CATEGORY_KEYS)
    summary, summary_source = _meta(
        soup,
        ("name", "description"),
        ("property", "og:description"),
    )
    if not summary:
        summary, summary_source = _first_text(brand_nodes, ("description",))
    if not summary:
        paragraph = soup.find("p")
        summary = paragraph.get_text(" ", strip=True) if paragraph else ""
        summary_source = "first paragraph" if summary else ""
    language = str(soup.html.get("lang", "")).strip() if soup.html else ""

    evidence: list[SiteProfileEvidence] = []
    for field, value, source in (
        ("brand_name", brand_name, brand_source),
        ("category", category, category_source),
        ("summary", summary, summary_source),
        ("language", language, "html[lang]" if language else ""),
    ):
        if value:
            evidence.append(
                SiteProfileEvidence(
                    field=cast(
                        Literal["brand_name", "category", "summary", "language"],
                        field,
                    ),
                    value=value,
                    source=source,
                )
            )
    warnings: list[str] = []
    if not brand_name:
        warnings.append("官网未提供可靠的品牌名元数据，请手动确认。")
    if not category:
        warnings.append("官网未提供明确的品类结构化数据，请手动填写。")
    warnings.append("竞争对手不能仅从自有官网可靠判定，需要你确认。")
    return SiteProfileResponse(
        url=fetch_result.url,
        status=fetch_result.status,
        title=title,
        brand_name=brand_name,
        category=category,
        summary=summary[:1000],
        language=language,
        evidence=evidence,
        warnings=warnings,
    )


async def discover_site(req: SiteProfileRequest) -> SiteProfileResponse:
    url = _normalize_url(req.url)
    result = await _fetch_public_site(url)
    if not result.ok:
        if result.status:
            raise ValueError(f"网站返回 HTTP {result.status}，无法读取首页")
        raise ValueError("网站无法访问，请检查地址、DNS 或访问限制")
    return _extract_profile(result)
