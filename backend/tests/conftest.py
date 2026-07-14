"""测试夹具：内存 SQLite + FastAPI TestClient。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import keeplix.models  # noqa: F401  注册表
from keeplix.core.db import get_session
from keeplix.main import create_app


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def client(engine, monkeypatch):
    # API 集成测试必须完全离线、可重复。开发者本机 .env 中的真实 key
    # 不应让名为「stub」的测试意外访问外部 Provider。
    for variable in (
        "KEEPLIX_DEEPSEEK_API_KEY",
        "KEEPLIX_KIMI_API_KEY",
        "KEEPLIX_QWEN_API_KEY",
        "KEEPLIX_DASHSCOPE_API_KEY",
        "KEEPLIX_BAIDU_API_KEY",
        "KEEPLIX_VOLCENGINE_API_KEY",
    ):
        monkeypatch.setenv(variable, "")
    from keeplix.core.config import get_settings

    get_settings.cache_clear()
    app = create_app()

    def _get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture
def _qualified_citation_provider(monkeypatch):
    from keeplix.providers.base import CitedSource, EngineResponse

    class QualifiedProvider:
        acquisition = "api"
        measurement_scope = "citation"

        def __init__(self, engine_id: str, brand_name: str | None = None):
            self.engine_id = engine_id
            self.brand_name = brand_name or "keeplix"

        async def query(self, prompt: str) -> EngineResponse:
            return EngineResponse(
                answer_text=f"{self.brand_name} 可以回答：{prompt}",
                cited_sources=[CitedSource(url="https://keeplix.com")],
                raw={"provider": "qualified-test", "request_id": f"{self.engine_id}-1"},
            )

    def provider(engine_id: str, **kwargs):
        return QualifiedProvider(engine_id, kwargs.get("brand_name"))

    monkeypatch.setattr("keeplix.agents.citation_agent.get_provider", provider)
    monkeypatch.setattr("keeplix.services.citation_service.get_provider", provider)
    monkeypatch.setattr("keeplix.api.engines.get_provider", provider)
