"""Provider registry：按 engine_id 装配 provider，有 key 用真实，无 key 回退 stub。

加新引擎（见 docs/citation-engine.md §6）：
  1. 新建 providers/<engine>.py 实现 EngineProvider
  2. 在 _REAL_BUILDERS 注册「有 key → 用真实」的构造逻辑
"""

from __future__ import annotations

from collections.abc import Callable

from keeplix.core.config import Settings, get_settings
from keeplix.providers.baidu_search import BaiduSearchProvider
from keeplix.providers.base import EngineProvider
from keeplix.providers.deepseek import DeepSeekProvider
from keeplix.providers.kimi_web_search import KimiWebSearchProvider
from keeplix.providers.qwen_web_search import QwenWebSearchProvider
from keeplix.providers.stub import StubProvider

# 已知引擎目录（id → 展示名）。信源偏好等细节在 DB 的 Engine 表 / stub。
KNOWN_ENGINES: dict[str, str] = {
    "deepseek": "DeepSeek",
    "qwen": "通义千问",
    "kimi": "Kimi",
    "baidu_ernie": "文心一言",
    "doubao": "豆包",
    "yuanbao": "腾讯元宝",
    "chatgpt": "ChatGPT",
    "perplexity": "Perplexity",
}


def list_known_engines() -> dict[str, str]:
    return dict(KNOWN_ENGINES)


def _build_qwen(settings: Settings) -> EngineProvider | None:
    api_key = settings.dashscope_api_key or settings.qwen_api_key
    if not api_key or not settings.qwen_search_agent_id:
        return None
    return QwenWebSearchProvider(
        api_key,
        settings.qwen_search_agent_id,
        settings.qwen_search_agent_version,
    )


# 有 key 时构造真实 provider 的逻辑；返回 None 表示无 key → 回退 stub。
_REAL_BUILDERS: dict[str, Callable[[Settings], EngineProvider | None]] = {
    "deepseek": lambda s: (
        DeepSeekProvider(s.deepseek_api_key, s.deepseek_base_url, model=s.deepseek_model)
        if s.deepseek_api_key
        else None
    ),
    "qwen": _build_qwen,
    "kimi": lambda s: (
        KimiWebSearchProvider(s.kimi_api_key, s.kimi_base_url, s.kimi_model)
        if s.kimi_api_key
        else None
    ),
    "baidu_ernie": lambda s: (
        BaiduSearchProvider(
            s.baidu_api_key,
            s.baidu_search_base_url,
            s.baidu_search_model,
        )
        if s.baidu_api_key
        else None
    ),
}


def get_provider(
    engine_id: str,
    *,
    brand_name: str | None = None,
    brand_domains: list[str] | None = None,
    settings: Settings | None = None,
) -> EngineProvider:
    """返回该引擎的 provider。有真实实现且有 key → 真实，否则确定性 stub。"""
    settings = settings or get_settings()

    builder = _REAL_BUILDERS.get(engine_id)
    if builder is not None:
        real = builder(settings)
        if real is not None:
            return real

    return StubProvider(engine_id, brand_name=brand_name, brand_domains=brand_domains)
