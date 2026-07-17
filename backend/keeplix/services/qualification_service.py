"""Provider surface qualification and formal-report eligibility."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import TypedDict, cast

import yaml
from sqlmodel import Session, select

from keeplix.models import Engine, EngineQualification
from keeplix.models.enums import Acquisition
from keeplix.providers import list_known_engines

_PROFILE_PATH = Path(__file__).parents[1] / "config" / "provider_validation.zh.yaml"


class ValidationProfile(TypedDict):
    surface_name: str
    expected_acquisition: str
    network_enabled: bool
    region_language: str
    auth_mode: str
    citation_availability: str
    measurement_scope: str
    formal_report_eligible: bool
    cost_note: str
    min_answer_chars: int
    require_request_id: bool
    require_citations: bool
    prompts: list[str]


@cache
def load_validation_profiles() -> tuple[int, dict[str, ValidationProfile]]:
    with _PROFILE_PATH.open(encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        raise ValueError("Provider 验证配置格式无效")
    version = int(data.get("version", 1))
    return version, cast(dict[str, ValidationProfile], data["profiles"])


def get_validation_profile(engine_id: str) -> tuple[int, ValidationProfile] | None:
    version, profiles = load_validation_profiles()
    profile = profiles.get(engine_id)
    return (version, profile) if profile else None


def _ensure_engine(engine_id: str, session: Session) -> Engine:
    engine = session.get(Engine, engine_id)
    if engine is not None:
        return engine
    profile_entry = get_validation_profile(engine_id)
    expected = profile_entry[1]["expected_acquisition"] if profile_entry else "stub"
    try:
        acquisition = Acquisition(expected)
    except ValueError:
        acquisition = Acquisition.stub
    engine = Engine(
        id=engine_id,
        display_name=list_known_engines().get(engine_id, engine_id),
        acquisition=acquisition,
    )
    session.add(engine)
    session.commit()
    session.refresh(engine)
    return engine


def get_qualification(engine_id: str, session: Session) -> EngineQualification:
    _ensure_engine(engine_id, session)
    qualification = session.get(EngineQualification, engine_id)
    profile_entry = get_validation_profile(engine_id)
    profile = profile_entry[1] if profile_entry else None
    if qualification:
        if not qualification.cost_note and profile:
            qualification.cost_note = profile["cost_note"]
            qualification.updated_at = datetime.now(UTC)
            session.add(qualification)
            session.commit()
            session.refresh(qualification)
        return qualification

    qualification = EngineQualification(
        engine_id=engine_id,
        surface_name=profile["surface_name"] if profile else engine_id,
        expected_acquisition=profile["expected_acquisition"] if profile else "stub",
        network_enabled=profile["network_enabled"] if profile else False,
        region_language=profile["region_language"] if profile else "zh-CN",
        auth_mode=profile["auth_mode"] if profile else "api_key",
        citation_availability=profile["citation_availability"] if profile else "none",
        measurement_scope=profile["measurement_scope"] if profile else "stub",
        validation_status="pending",
        report_eligible=False,
        validation_notes="尚未完成带证据的 Provider 验证与人工审核。",
        cost_note=profile["cost_note"] if profile else "当前未提供正式成本说明。",
    )
    session.add(qualification)
    session.commit()
    session.refresh(qualification)
    return qualification


def list_qualifications(session: Session) -> list[EngineQualification]:
    return list(session.exec(select(EngineQualification)).all())


def is_formally_eligible(
    qualification: EngineQualification, acquisition: str, measurement_scope: str
) -> bool:
    return bool(
        qualification.report_eligible
        and qualification.validation_status == "accepted"
        and acquisition != "stub"
        and acquisition == qualification.expected_acquisition
        and measurement_scope == qualification.measurement_scope
        and measurement_scope in {"answer_visibility", "citation"}
    )
