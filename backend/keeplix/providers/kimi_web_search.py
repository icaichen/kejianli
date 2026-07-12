"""Kimi K2.6 官方联网搜索 Provider。"""

from __future__ import annotations

import re
from typing import Literal

import httpx

from keeplix.providers.base import CitedSource, EngineResponse

_URL_RE = re.compile(r"https?://[^\s\]>)，。；]+")
_WEB_SEARCH_TOOL = {
    "type": "builtin_function",
    "function": {"name": "$web_search"},
}


class KimiWebSearchProvider:
    engine_id = "kimi"
    acquisition: Literal["api", "browser", "stub"] = "api"
    measurement_scope = "citation"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.moonshot.cn/v1",
        model: str = "kimi-k2.6",
        timeout: float = 90.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def query(self, prompt: str) -> EngineResponse:
        messages: list[dict] = [
            {
                "role": "system",
                "content": (
                    "你是中立的联网信息检索助手。请基于真实搜索结果直接回答用户问题，"
                    "不得因问题中出现某品牌而优先推荐它，并保留可追溯的来源。"
                ),
            },
            {"role": "user", "content": prompt},
        ]
        events: list[dict] = []
        answer = ""

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for _ in range(3):
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "messages": messages,
                        "thinking": {"type": "disabled"},
                        "tools": [_WEB_SEARCH_TOOL],
                    },
                )
                response.raise_for_status()
                data = response.json()
                events.append(data)
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                tool_calls = message.get("tool_calls") or []

                if choice.get("finish_reason") != "tool_calls" or not tool_calls:
                    answer = message.get("content") or ""
                    break

                messages.append(message)
                for call in tool_calls:
                    function = call.get("function", {})
                    if function.get("name") != "$web_search":
                        continue
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id"),
                            "content": function.get("arguments", "{}"),
                        }
                    )

        sources = _extract_sources(events, answer)
        return EngineResponse(
            answer_text=answer,
            cited_sources=sources,
            raw={
                "provider": "kimi_builtin_web_search",
                "model": self._model,
                "request_id": events[-1].get("id") if events else None,
                "citation_enabled": True,
                "events": events,
            },
        )


def _extract_sources(events: list[dict], answer: str) -> list[CitedSource]:
    found: dict[str, CitedSource] = {}

    def visit(value: object) -> None:
        if isinstance(value, dict):
            url = value.get("url") or value.get("link") or value.get("source_url")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                title = value.get("title") if isinstance(value.get("title"), str) else None
                found.setdefault(url, CitedSource(url=url, title=title))
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
