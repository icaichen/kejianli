"""DeepSeekProvider：示例真实 provider（acquisition=api）。

有 KEEPLIX_DEEPSEEK_API_KEY 时 registry 用它，否则回退 StubProvider。
DeepSeek 兼容 OpenAI Chat Completions 格式。联网/引用能力随官方接口演进，
本实现先取回答文本；cited_sources 的解析在接入联网检索后补齐（见 docs/citation-engine.md §6）。
"""

from __future__ import annotations

from typing import Literal

import httpx

from keeplix.providers.base import CitedSource, EngineResponse


class DeepSeekProvider:
    engine_id = "deepseek"
    acquisition: Literal["api", "browser", "stub"] = "api"
    measurement_scope = "brand_awareness"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def query(self, prompt: str) -> EngineResponse:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        cited = _extract_cited_sources(data)
        return EngineResponse(answer_text=answer, cited_sources=cited, raw=data)


def _extract_cited_sources(data: dict) -> list[CitedSource]:
    """从响应中解析引用来源。联网检索开启后官方会返回来源，此处做防御式解析。"""
    sources: list[CitedSource] = []
    for ref in data.get("references", []) or []:
        url = ref.get("url")
        if url:
            sources.append(CitedSource(url=url, title=ref.get("title")))
    return sources
