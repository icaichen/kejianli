"""GET /api/engines —— 列出已知引擎及其当前 provider 是真实还是 stub。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from keeplix.providers import get_provider, list_known_engines

router = APIRouter(tags=["engines"])


class EngineInfo(BaseModel):
    id: str
    display_name: str
    acquisition: str
    is_stub: bool


@router.get("/engines", response_model=list[EngineInfo])
def index() -> list[EngineInfo]:
    out: list[EngineInfo] = []
    for engine_id, name in list_known_engines().items():
        provider = get_provider(engine_id)
        out.append(
            EngineInfo(
                id=engine_id,
                display_name=name,
                acquisition=getattr(provider, "acquisition", "stub"),
                is_stub=getattr(provider, "acquisition", "stub") == "stub",
            )
        )
    return out
