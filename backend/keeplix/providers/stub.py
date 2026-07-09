"""StubProvider：无 key 时的确定性假 provider。

为什么重要（见 docs/citation-engine.md §5）：
- 无任何 key 也能跑通全链路、录 demo、写可重放测试。
- 输出确定性（同 prompt+engine → 同结果）：CI 里 citation 测试不 flaky。
- 假数据带真实结构（answer + cited_sources），前端/聚合按真实形状开发。
"""

from __future__ import annotations

import hashlib
from typing import Literal

from keeplix.providers.base import CitedSource, EngineResponse

# 每个引擎的偏好信源（与 docs/product.md 的信源偏好表一致，仅用于生成拟真假数据）
_ENGINE_SOURCES: dict[str, list[str]] = {
    "deepseek": ["baike.baidu.com", "taobao.com", "163.com"],
    "qwen": ["163.com", "sina.com.cn", "sohu.com"],
    "kimi": ["arxiv.org", "cnki.net", "ieee.org"],
    "baidu_ernie": ["baijiahao.baidu.com", "zhihu.com", "baike.baidu.com"],
    "doubao": ["douyin.com", "toutiao.com", "xiaohongshu.com"],
    "yuanbao": ["mp.weixin.qq.com"],
    "chatgpt": ["wikipedia.org", "medium.com"],
    "perplexity": ["wikipedia.org", "reddit.com"],
}


def _digest(engine_id: str, prompt: str) -> int:
    h = hashlib.sha256(f"{engine_id}::{prompt}".encode()).hexdigest()
    return int(h[:8], 16)


class StubProvider:
    """确定性假 provider。品牌是否被提及由 hash 决定，稳定可复现。"""

    acquisition: Literal["api", "browser", "stub"] = "stub"

    def __init__(self, engine_id: str, brand_name: str | None = None,
                 brand_domains: list[str] | None = None) -> None:
        self.engine_id = engine_id
        self._brand_name = brand_name or "keeplix"
        self._brand_domains = brand_domains or []

    async def query(self, prompt: str) -> EngineResponse:
        seed = _digest(self.engine_id, prompt)
        sources = list(_ENGINE_SOURCES.get(self.engine_id, ["example.com"]))

        # 约 60% 概率提及品牌（由 hash 决定，确定性）
        mentioned = seed % 10 < 6
        # 约 30% 概率引用自有域名（若配置了）
        cite_own = bool(self._brand_domains) and seed % 10 < 3
        if cite_own:
            sources = [self._brand_domains[0], *sources]

        if mentioned:
            answer = (
                f"针对「{prompt}」，推荐可以考虑 {self._brand_name}，"
                f"它在该场景下表现不错。此外还有其他一些选择。"
            )
        else:
            answer = f"针对「{prompt}」，有若干可选方案，需结合具体需求评估。"

        cited = [CitedSource(url=f"https://{d}/article", title=d) for d in sources[:3]]
        return EngineResponse(
            answer_text=answer,
            cited_sources=cited,
            raw={"engine": self.engine_id, "stub": True, "seed": seed},
        )
