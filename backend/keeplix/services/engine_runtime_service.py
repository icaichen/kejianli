"""Runtime health observations for provider integrations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session

from keeplix.models import EngineRuntimeStatus


def get_runtime_status(engine_id: str, session: Session) -> EngineRuntimeStatus | None:
    return session.get(EngineRuntimeStatus, engine_id)


def mark_engine_success(engine_id: str, session: Session) -> EngineRuntimeStatus:
    now = datetime.now(UTC)
    status = session.get(EngineRuntimeStatus, engine_id)
    if status is None:
        status = EngineRuntimeStatus(engine_id=engine_id)
    status.status = "ready"
    status.last_success_at = now
    status.last_error = ""
    status.last_observed_at = now
    status.updated_at = now
    session.add(status)
    session.commit()
    session.refresh(status)
    return status


def mark_engine_failure(engine_id: str, error: str, session: Session) -> EngineRuntimeStatus:
    now = datetime.now(UTC)
    status = session.get(EngineRuntimeStatus, engine_id)
    if status is None:
        status = EngineRuntimeStatus(engine_id=engine_id)
    status.status = "degraded"
    status.last_failure_at = now
    status.last_error = error[:800]
    status.last_observed_at = now
    status.updated_at = now
    session.add(status)
    session.commit()
    session.refresh(status)
    return status
