"""百度千帆智能搜索生成 Provider（带结构化网页引用）。"""

from __future__ import annotations

from typing import Literal

import httpx

from keeplix.providers.base import CitedSource, EngineResponse


class BaiduSearchProvider:
    engine_id = "baidu_ernie"
    acquisition: Literal["api", "browser", "stub"] = "api"
    measurement_scope = "citation"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://qianfan.baidubce.com/v2/ai_search",
        model: str = "ernie-4.5-turbo-32k",
        timeout: float = 90.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def query(self, prompt: str) -> EngineResponse:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers={"X-Appbuilder-Authorization": f"Bearer {self._api_key}"},
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "search_source": "baidu_search_v1",
                    "resource_type_filter": [{"type": "web", "top_k": 10}],
                    "stream": False,
                    "model": self._model,
                    "enable_deep_search": False,
                    "enable_followup_query": False,
                    "enable_corner_markers": True,
                    "search_mode": "auto",
                },
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        return EngineResponse(
            answer_text=message.get("content") or "",
            cited_sources=_extract_sources(data.get("references") or []),
            raw={
                "provider": "baidu_ai_search",
                "model": self._model,
                "request_id": _request_id(data),
                "citation_enabled": True,
                "response": data,
            },
        )


def _extract_sources(references: list[object]) -> list[CitedSource]:
    found: dict[str, CitedSource] = {}
    for reference in references:
        if not isinstance(reference, dict):
            continue
        url = reference.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        title = reference.get("title")
        found.setdefault(
            url,
            CitedSource(url=url, title=title if isinstance(title, str) else None),
        )
    return list(found.values())


def _request_id(data: dict[str, object]) -> str | None:
    for key in ("request_id", "requestId", "request_Id"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None
