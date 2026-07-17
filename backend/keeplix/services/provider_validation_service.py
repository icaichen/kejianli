"""Run evidence-backed Provider checks and apply explicit human review decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from keeplix.models import EngineQualification, EngineValidationRun
from keeplix.providers import get_provider
from keeplix.providers.base import EngineResponse
from keeplix.services.engine_runtime_service import mark_engine_failure, mark_engine_success
from keeplix.services.qualification_service import (
    ValidationProfile,
    get_qualification,
    get_validation_profile,
)


def _is_web_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _safe_error(error: Exception) -> str:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code:
        return f"Provider 请求失败（HTTP {status_code}）"
    return f"Provider 请求失败（{type(error).__name__}）"


def _provider_metadata(response: EngineResponse, provider_name: str) -> dict[str, object]:
    raw = response.raw if isinstance(response.raw, dict) else {}
    request_id = raw.get("request_id") or raw.get("id")
    model = raw.get("model")
    return {
        "provider": raw.get("provider") or provider_name,
        "request_id": request_id if isinstance(request_id, str) else None,
        "model": model if isinstance(model, str) else None,
        "agent_id": raw.get("agent_id") if isinstance(raw.get("agent_id"), str) else None,
        "agent_version": (
            raw.get("agent_version") if isinstance(raw.get("agent_version"), str) else None
        ),
        "citation_enabled": (
            raw.get("citation_enabled")
            if isinstance(raw.get("citation_enabled"), bool)
            else None
        ),
    }


def _build_evidence(
    prompt: str, response: EngineResponse, provider_name: str, observed_at: datetime
) -> dict[str, object]:
    return {
        "prompt": prompt,
        "answer_text": response.answer_text,
        "cited_urls": [source.url for source in response.cited_sources],
        "provider_metadata": _provider_metadata(response, provider_name),
        "observed_at": observed_at.isoformat(),
    }


def _evaluate(
    evidence: list[dict],
    profile: ValidationProfile,
    acquisition: str,
    measurement_scope: str,
) -> dict[str, bool]:
    has_all_evidence = len(evidence) == len(profile["prompts"])
    metadata = [item.get("provider_metadata", {}) for item in evidence]
    cited_urls = [item.get("cited_urls", []) for item in evidence]
    answers_complete = has_all_evidence and all(
        isinstance(item.get("answer_text"), str)
        and len(str(item["answer_text"]).strip()) >= profile["min_answer_chars"]
        for item in evidence
    )
    request_ids_present = not profile["require_request_id"] or (
        has_all_evidence
        and all(isinstance(item, dict) and bool(item.get("request_id")) for item in metadata)
    )
    citations_present = not profile["require_citations"] or (
        has_all_evidence
        and all(isinstance(urls, list) and bool(urls) for urls in cited_urls)
    )
    citation_urls_valid = has_all_evidence and all(
        isinstance(urls, list)
        and all(isinstance(url, str) and _is_web_url(url) for url in urls)
        for urls in cited_urls
    )
    surface_identity_present = has_all_evidence and all(
        isinstance(item, dict)
        and bool(item.get("provider"))
        and bool(item.get("model") or item.get("agent_id"))
        for item in metadata
    )
    network_evidenced = not profile["network_enabled"] or (
        has_all_evidence
        and all(
            isinstance(urls, list) and bool(urls) and _metadata_citation_enabled(item)
            for urls, item in zip(cited_urls, metadata, strict=True)
        )
    )
    return {
        "provider_connected": acquisition != "stub",
        "acquisition_matches": acquisition == profile["expected_acquisition"],
        "measurement_scope_matches": measurement_scope == profile["measurement_scope"],
        "answers_complete": answers_complete,
        "request_ids_present": request_ids_present,
        "citations_present": citations_present,
        "citation_urls_valid": citation_urls_valid,
        "surface_identity_present": surface_identity_present,
        "network_evidenced": network_evidenced,
        "normalized_shape_consistent": has_all_evidence,
    }


def _metadata_citation_enabled(value: object) -> bool:
    return isinstance(value, dict) and value.get("citation_enabled") is not False


async def run_provider_validation(engine_id: str, session: Session) -> EngineValidationRun:
    profile_entry = get_validation_profile(engine_id)
    if profile_entry is None:
        raise ValueError("该引擎尚未配置 Provider 验证题集")
    profile_version, profile = profile_entry
    qualification = get_qualification(engine_id, session)
    active_run = session.exec(
        select(EngineValidationRun).where(
            EngineValidationRun.engine_id == engine_id,
            EngineValidationRun.status == "running",
        )
    ).first()
    if active_run is not None:
        raise ValueError("该答案面已有验证正在运行，请等待完成后再试")
    now = datetime.now(UTC)
    superseded_runs = session.exec(
        select(EngineValidationRun).where(
            EngineValidationRun.engine_id == engine_id,
            EngineValidationRun.review_status == "pending",
        )
    ).all()
    for superseded in superseded_runs:
        superseded.review_status = "rejected"
        superseded.reviewed_at = now
        superseded.review_notes = "已被更新的 Provider 验证替代。"
        session.add(superseded)
    provider = get_provider(engine_id)
    acquisition = str(getattr(provider, "acquisition", "stub"))
    measurement_scope = str(getattr(provider, "measurement_scope", "stub"))

    qualification.validation_status = "pending"
    qualification.report_eligible = False
    qualification.last_validated_at = None
    qualification.validation_notes = "Provider 验证已运行，等待人工审核证据。"
    qualification.updated_at = now
    run = EngineValidationRun(
        engine_id=engine_id,
        profile_version=profile_version,
        provider_acquisition=acquisition,
        measurement_scope=measurement_scope,
        started_at=now,
    )
    session.add(qualification)
    session.add(run)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ValueError("该答案面已有验证正在运行，请等待完成后再试") from error
    session.refresh(run)

    evidence: list[dict] = []
    error_summary = ""
    if acquisition == "stub":
        error_summary = "未连接真实 Provider；stub 仅用于演示，不能完成资格验证。"
    else:
        try:
            for prompt in profile["prompts"]:
                response = await provider.query(prompt)
                evidence.append(
                    _build_evidence(
                        prompt,
                        response,
                        type(provider).__name__,
                        datetime.now(UTC),
                    )
                )
            mark_engine_success(engine_id, session)
        except Exception as error:
            error_summary = _safe_error(error)
            mark_engine_failure(engine_id, error_summary, session)

    checks = _evaluate(evidence, profile, acquisition, measurement_scope)
    run.evidence = evidence
    run.checks = checks
    run.error_summary = error_summary
    run.status = "passed" if not error_summary and all(checks.values()) else "failed"
    run.finished_at = datetime.now(UTC)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def list_provider_validations(engine_id: str, session: Session) -> list[EngineValidationRun]:
    return list(
        session.exec(
            select(EngineValidationRun)
            .where(EngineValidationRun.engine_id == engine_id)
            .order_by(col(EngineValidationRun.started_at).desc())
        ).all()
    )


def review_provider_validation(
    engine_id: str,
    validation_id: str,
    decision: str,
    notes: str,
    session: Session,
) -> EngineValidationRun:
    run = session.get(EngineValidationRun, validation_id)
    if run is None or run.engine_id != engine_id:
        raise LookupError("未找到 Provider 验证记录")
    latest = session.exec(
        select(EngineValidationRun)
        .where(EngineValidationRun.engine_id == engine_id)
        .order_by(col(EngineValidationRun.started_at).desc())
    ).first()
    if latest is None or latest.id != run.id:
        raise ValueError("只能审核该引擎最新的验证记录")
    if run.review_status != "pending":
        raise ValueError("该验证记录已经审核，审核结果不可覆盖")
    if decision == "accepted" and run.status != "passed":
        raise ValueError("未通过自动检查的验证记录不能标记为已接受")

    profile_entry = get_validation_profile(engine_id)
    if profile_entry is None:
        raise ValueError("该引擎尚未配置 Provider 验证题集")
    profile_version, profile = profile_entry
    if run.profile_version != profile_version:
        raise ValueError("验证配置已更新，请重新运行后再审核")

    qualification: EngineQualification = get_qualification(engine_id, session)
    reviewed_at = datetime.now(UTC)
    run.review_status = decision
    run.reviewed_at = reviewed_at
    run.review_notes = notes
    qualification.validation_status = decision
    qualification.report_eligible = bool(
        decision == "accepted" and profile["formal_report_eligible"]
    )
    qualification.last_validated_at = run.finished_at
    qualification.validation_notes = notes
    qualification.updated_at = reviewed_at
    session.add(run)
    session.add(qualification)
    session.commit()
    session.refresh(run)
    return run
