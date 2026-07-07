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
def client(engine):
    app = create_app()

    def _get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    with TestClient(app) as c:
        yield c
