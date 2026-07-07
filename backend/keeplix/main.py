"""FastAPI 应用入口。启动：uv run uvicorn keeplix.main:app --reload"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from keeplix.api import api_router
from keeplix.core.config import get_settings
from keeplix.core.db import init_db
from keeplix.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # 骨架阶段：确保表存在（生产用 alembic upgrade head）
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="keeplix API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    app.include_router(api_router)
    return app


app = create_app()
