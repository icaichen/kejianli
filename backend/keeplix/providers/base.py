"""EngineProvider 抽象：屏蔽「有的有 API、有的只能抓浏览器、有的还没接」。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Acquisition = Literal["api", "browser", "stub"]


@dataclass
class CitedSource:
    url: str
    title: str | None = None


@dataclass
class EngineResponse:
    """一次引擎查询的归一化结果。"""

    answer_text: str
    cited_sources: list[CitedSource] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@runtime_checkable
class EngineProvider(Protocol):
    """所有引擎适配器实现此协议。"""

    engine_id: str
    acquisition: Acquisition

    async def query(self, prompt: str) -> EngineResponse:
        """对引擎发起一次查询，返回归一化响应。"""
        ...
