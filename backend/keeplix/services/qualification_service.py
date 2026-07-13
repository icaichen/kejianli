"""Provider surface qualification and formal-report eligibility."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from keeplix.models import EngineQualification

QUALIFICATION_DEFAULTS: dict[str, dict[str, object]] = {
    "qwen": {
        "surface_name": "千问联网检索 Agent",
        "expected_acquisition": "api",
        "network_enabled": True,
        "citation_availability": "structured",
        "measurement_scope": "citation",
        "validation_status": "accepted",
        "report_eligible": True,
        "validation_notes": "已对照真实联网回答、引用 URL、请求 ID 与原始 SSE 事件。",
        "cost_note": "按千问 Agent 调用计费；采样次数越高，成本越高。",
    },
    "kimi": {
        "surface_name": "Kimi K2.6 $web_search",
        "expected_acquisition": "api",
        "network_enabled": True,
        "citation_availability": "urls",
        "measurement_scope": "citation",
        "validation_status": "accepted",
        "report_eligible": True,
        "validation_notes": "已验收两阶段联网搜索事件、来源 URL 与请求 ID。",
        "cost_note": "按 Moonshot API 用量计费；账户余额不足时会返回 429。",
    },
    "baidu_ernie": {
        "surface_name": "百度智能搜索生成",
        "expected_acquisition": "api",
        "network_enabled": True,
        "citation_availability": "structured",
        "measurement_scope": "citation",
        "validation_status": "accepted",
        "report_eligible": True,
        "validation_notes": "已验收联网回答、结构化 references 与请求 ID。",
        "cost_note": "按百度智能搜索调用计费；以控制台当前套餐为准。",
    },
    "deepseek": {
        "surface_name": "DeepSeek Chat API",
        "expected_acquisition": "api",
        "network_enabled": False,
        "citation_availability": "none",
        "measurement_scope": "brand_awareness",
        "validation_status": "accepted",
        "report_eligible": False,
        "validation_notes": "仅验收普通模型回答采样，不具备搜索引用报告资格。",
        "cost_note": "普通聊天调用可用于品牌认知，不可替代搜索引用追踪。",
    },
}


def get_qualification(engine_id: str, session: Session) -> EngineQualification:
    qualification = session.get(EngineQualification, engine_id)
    if qualification:
        # Backfill non-decision display metadata for rows created before the
        # qualification matrix was exposed. Do not change acceptance status.
        defaults = QUALIFICATION_DEFAULTS.get(engine_id, {})
        if not qualification.cost_note and defaults.get("cost_note"):
            qualification.cost_note = str(defaults["cost_note"])
            qualification.updated_at = datetime.now(UTC)
            session.add(qualification)
            session.commit()
            session.refresh(qualification)
        return qualification
    defaults = QUALIFICATION_DEFAULTS.get(engine_id, {})
    qualification = EngineQualification(
        engine_id=engine_id,
        surface_name=str(defaults.get("surface_name", engine_id)),
        expected_acquisition=str(defaults.get("expected_acquisition", "stub")),
        network_enabled=bool(defaults.get("network_enabled", False)),
        citation_availability=str(defaults.get("citation_availability", "none")),
        measurement_scope=str(defaults.get("measurement_scope", "stub")),
        validation_status=str(defaults.get("validation_status", "pending")),
        report_eligible=bool(defaults.get("report_eligible", False)),
        last_validated_at=(
            datetime(2026, 7, 12, tzinfo=UTC)
            if defaults.get("validation_status") == "accepted"
            else None
        ),
        validation_notes=str(defaults.get("validation_notes", "尚未完成人工对照验收。")),
        cost_note=str(defaults.get("cost_note", "当前未提供正式成本说明。")),
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
