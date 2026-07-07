"""全局配置。所有密钥/开关走环境变量（`.env`），无 key 时系统仍完整可跑（全 stub）。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KEEPLIX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 基础 ---
    app_name: str = "keeplix"
    database_url: str = "sqlite:///./keeplix.db"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Citation 采样 ---
    citation_samples: int = 3

    # --- 模型 key（有则对应引擎切真实，无则 stub）---
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    qwen_api_key: str | None = None
    kimi_api_key: str | None = None
    openai_api_key: str | None = None
    perplexity_api_key: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
