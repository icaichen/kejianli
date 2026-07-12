"""千问联网检索 Agent Provider。

这是第一个正式的「答案面」Provider：强制联网、开启引用、保存完整 SSE 事件，
以便每一条 GEO 指标都能回溯到原始回答和来源证据。
"""

from __future__ import annotations

import json
import re
from typing import Literal

import httpx

from keeplix.providers.base import CitedSource, EngineResponse

_ENDPOINT = "https://dashscope.aliyuncs.com/api/v2/apps/web-search-agent/chat/completions"
_URL_RE = re.compile(r"https?://[^\s\]>)，。；]+")


class QwenWebSearchProvider:
    engine_id = "qwen"
    acquisition: Literal["api", "browser", "stub"] = "api"
    measurement_scope = "citation"

    def __init__(
        self, api_key: str, agent_id: str, agent_version: str = "release", timeout: float = 90.0
    ) -> None:
        self._api_key = api_key
        self._agent_id = agent_id
        self._agent_version = agent_version
        self._timeout = timeout

    async def query(self, prompt: str) -> EngineResponse:
        payload = {
            "input": {"messages": [{"role": "user", "content": prompt}]},
            "parameters": {
                "agent_options": {
                    "agent_id": self._agent_id,
                    "agent_version": self._agent_version,
                    "forced_search": True,
                    "enable_citation": True,
                    "enable_text_image_mixed": False,
                    "enable_rec_question": False,
                }
            },
            "stream": True,
        }
        events: list[dict] = []
        text_parts: list[str] = []
        request_id: str | None = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                _ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    events.append(event)
                    request_id = event.get("request_id") or request_id
                    for choice in event.get("output", {}).get("choices", []):
                        message = choice.get("message", {})
                        if message.get("role") == "assistant" and isinstance(
                            message.get("content"), str
                        ):
                            _append_delta(text_parts, message["content"])

        answer = "".join(text_parts).strip()
        sources = _extract_sources(events, answer)
        return EngineResponse(
            answer_text=answer,
            cited_sources=sources,
            raw={
                "provider": "qwen_web_search_agent",
                "request_id": request_id,
                "agent_id": self._agent_id,
                "agent_version": self._agent_version,
                "citation_enabled": True,
                "events": events,
            },
        )


def _append_delta(parts: list[str], value: str) -> None:
    """SSE 可能传增量，也可能重传累计文本；两种形式都避免重复。"""
    if not value:
        return
    current = "".join(parts)
    if value.startswith(current):
        parts[:] = [value]
    elif not current.endswith(value):
        parts.append(value)


def _extract_sources(events: list[dict], answer: str) -> list[CitedSource]:
    found: dict[str, CitedSource] = {}

    def visit(value: object) -> None:
        if isinstance(value, dict):
            url = value.get("url") or value.get("link") or value.get("source_url")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                found.setdefault(
                    url,
                    CitedSource(
                        url=url,
                        title=value.get("title") if isinstance(value.get("title"), str) else None,
                    ),
                )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            for url in _URL_RE.findall(value):
                found.setdefault(url, CitedSource(url=url))

    visit(events)
    visit(answer)
    return list(found.values())
