"""全局配置。所有密钥/开关走环境变量（`.env`），无 key 时系统仍完整可跑（全 stub）。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KEEPLIX_",
        # 本地统一凭证放项目根 .env；backend/.env 可覆盖同名值，便于服务独立部署。
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 基础 ---
    app_name: str = "keeplix"
    database_url: str = "sqlite:///./keeplix.db"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Citation 采样 ---
    citation_samples: int = 3

    # --- 抓取 ---
    # 显式开启浏览器抓取（需要 uv sync --extra browser 装 Playwright）。
    # 默认关：只用 httpx，快且零依赖。SSR 客户站点再打开。
    use_browser: bool = False
    fetch_user_agent: str = "keeplix-bot/0.1 (+https://keeplix.example)"

    # --- 模型 key（有则对应引擎切真实，无则 stub）---
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    # 官方当前推荐 V4；旧 deepseek-chat/deepseek-reasoner 将于 2026-07-24 下线。
    deepseek_model: str = "deepseek-v4-flash"
    qwen_api_key: str | None = None
    dashscope_api_key: str | None = None
    qwen_search_agent_id: str | None = None
    qwen_search_agent_version: str = "release"
    kimi_api_key: str | None = None
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "kimi-k2.6"
    baidu_api_key: str | None = None
    baidu_search_base_url: str = "https://qianfan.baidubce.com/v2/ai_search"
    baidu_search_model: str = "ernie-4.5-turbo-32k"
    openai_api_key: str | None = None
    perplexity_api_key: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
