"""GET /api/engines —— 列出已知引擎及其当前 provider 是真实还是 stub。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from keeplix.core.db import get_session
from keeplix.providers import get_provider, list_known_engines
from keeplix.services.qualification_service import (
    get_qualification,
    is_formally_eligible,
)

router = APIRouter(tags=["engines"])


class EngineInfo(BaseModel):
    id: str
    display_name: str
    acquisition: str
    is_stub: bool
    measurement_scope: str
    surface_name: str
    network_enabled: bool
    region_language: str
    auth_mode: str
    citation_availability: str
    validation_status: str
    report_eligible: bool
    last_validated_at: str | None
    validation_notes: str
    cost_note: str


@router.get("/engines", response_model=list[EngineInfo])
def index(session: Session = Depends(get_session)) -> list[EngineInfo]:
    out: list[EngineInfo] = []
    for engine_id, name in list_known_engines().items():
        provider = get_provider(engine_id)
        acquisition = str(getattr(provider, "acquisition", "stub"))
        measurement_scope = str(getattr(provider, "measurement_scope", "stub"))
        qualification = get_qualification(engine_id, session)
        out.append(
            EngineInfo(
                id=engine_id,
                display_name=name,
                acquisition=acquisition,
                is_stub=acquisition == "stub",
                measurement_scope=measurement_scope,
                surface_name=qualification.surface_name,
                network_enabled=qualification.network_enabled,
                region_language=qualification.region_language,
                auth_mode=qualification.auth_mode,
                citation_availability=qualification.citation_availability,
                validation_status=qualification.validation_status,
                report_eligible=is_formally_eligible(qualification, acquisition, measurement_scope),
                last_validated_at=(
                    qualification.last_validated_at.isoformat()
                    if qualification.last_validated_at
                    else None
                ),
                validation_notes=qualification.validation_notes,
                cost_note=qualification.cost_note,
            )
        )
    return out
