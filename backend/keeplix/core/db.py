"""数据库 session。默认 SQLite（零外部依赖），生产可切 Postgres（改 KEEPLIX_DATABASE_URL）。"""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from keeplix.core.config import get_settings

_settings = get_settings()

# SQLite 需要 check_same_thread=False 以配合 FastAPI 的线程模型
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}

engine = create_engine(_settings.database_url, connect_args=_connect_args)


def init_db() -> None:
    """建表（开发/测试用；生产用 Alembic 迁移）。"""
    # 确保所有模型已注册到 SQLModel.metadata
    import keeplix.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI 依赖：产出一个 DB session。"""
    with Session(engine) as session:
        yield session
