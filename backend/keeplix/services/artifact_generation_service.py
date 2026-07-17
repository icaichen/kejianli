"""使用正式诊断与已验证品牌事实生成可审批优化产物。"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlmodel import Session, select

from keeplix.models import (
    BrandEntity,
    BrandFact,
    OptimizationArtifact,
    Project,
    ProjectActivity,
    WorkItem,
)
from keeplix.models.enums import RunStatus
from keeplix.providers import get_provider
from keeplix.schemas import ArtifactGenerateRequest, OptimizationArtifactDTO
from keeplix.services.engine_runtime_service import mark_engine_failure, mark_engine_success


def _artifact_dto(artifact: OptimizationArtifact) -> OptimizationArtifactDTO:
    return OptimizationArtifactDTO.model_validate(artifact, from_attributes=True)


def _parse_json_object(value: str) -> dict:
    stripped = value.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1]).strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("生成引擎未返回有效 JSON-LD")
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as error:
        raise ValueError("生成引擎返回的 JSON-LD 无法解析") from error
    if not isinstance(parsed, dict):
        raise ValueError("生成引擎未返回 JSON 对象")
    return parsed


def _generation_error(error: Exception) -> ValueError:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code == 429:
        return ValueError("生成引擎当前限频或额度不足，请稍后重试或切换引擎")
    if status_code in {401, 403}:
        return ValueError("生成引擎鉴权失败，请检查 API 密钥和访问权限")
    if isinstance(status_code, int) and status_code >= 500:
        return ValueError("生成引擎服务暂时不可用，请稍后重试")
    return ValueError("生成引擎调用失败，请检查连接状态和账户额度")


async def generate_artifact(
    project_id: str,
    work_item_id: str,
    req: ArtifactGenerateRequest,
    session: Session,
) -> OptimizationArtifactDTO:
    project = session.get(Project, project_id)
    item = session.get(WorkItem, work_item_id)
    if project is None or item is None or item.project_id != project_id:
        raise ValueError("优化工作不存在")
    evidence_version = int((item.evidence_snapshot or {}).get("brief_version", 1))
    if evidence_version != project.brief_version:
        raise ValueError("该优化工作属于旧研究 Brief，请先建立当前基线")
    facts = session.exec(
        select(BrandFact).where(
            BrandFact.project_id == project_id,
            BrandFact.status == "verified",
        )
    ).all()
    if not facts:
        raise ValueError("请先在项目中添加至少一条已验证品牌事实")
    provider = get_provider(req.engine_id)
    if provider.acquisition == "stub":
        raise ValueError("不能使用 Stub Provider 生成客户产物")
    brand = session.exec(
        select(BrandEntity).where(BrandEntity.project_id == project_id)
    ).first()
    brand_name = brand.brand_name if brand else project.name
    fact_payload = [
        {
            "id": fact.id,
            "type": fact.fact_type,
            "claim": fact.claim,
            "source_url": fact.source_url,
        }
        for fact in facts
    ]
    evidence = item.evidence_snapshot or {}
    format_instruction = {
        "content": (
            "输出一份可编辑的 Markdown 内容草稿，包含直接回答、适用场景、"
            "可验证的产品事实、局限和事实来源。"
        ),
        "instructions": (
            "输出一份 Markdown 执行说明。首先用表格逐字列出每条已验证事实及其 URL，"
            "再明确当前诊断、仍缺失的事实、可在现有来源页完成的改动、发布检查和"
            "严格复用原问题与原答案面的复测方法。事实不足时不得指定新渠道或效果承诺。"
        ),
        "jsonld": (
            "只输出一个严格 JSON 对象，使用 schema.org 词汇。"
            "不得输出 Markdown 代码围栏或解释。"
        ),
    }[req.kind]
    prompt = (
        "你是企业 GEO 优化编辑。下列品牌事实已由用户确认，是唯一可用的"
        "事实来源。不得补充、推测或编造任何功能、数据、客户、价格或引用。"
        "观测证据只能证明该次回答实际出现的内容，不能用来推断平台偏好、索引时效、"
        "信源权威度、排名机制或预期效果。不得给出未被证据支持的天数、比例、渠道优先级或"
        "成功标准。可以提出待验证假设，但必须明确标记「待验证」及其验证方法。"
        "若事实不足，必须在产物中明确标记待补充项。\n\n"
        f"品牌：{brand_name}\n市场：{project.market}\n品类：{project.category}\n"
        f"优化工作：{item.title}\n诊断：{item.detail}\n"
        f"观测证据：{json.dumps(evidence, ensure_ascii=False)}\n"
        f"已验证事实：{json.dumps(fact_payload, ensure_ascii=False)}\n\n"
        f"{format_instruction}"
    )
    try:
        response = await provider.query(prompt)
    except Exception as error:
        safe_error = _generation_error(error)
        mark_engine_failure(req.engine_id, str(safe_error), session)
        raise safe_error from error
    mark_engine_success(req.engine_id, session)
    if not response.answer_text.strip():
        raise ValueError("生成引擎返回了空内容，未建立产物")
    structured_content = _parse_json_object(response.answer_text) if req.kind == "jsonld" else {}
    content = "" if req.kind == "jsonld" else response.answer_text.strip()
    previous = session.exec(
        select(OptimizationArtifact).where(
            OptimizationArtifact.work_item_id == item.id,
            OptimizationArtifact.kind == req.kind,
        )
    ).all()
    for artifact in previous:
        if artifact.status != "implemented":
            artifact.status = "superseded"
            session.add(artifact)
    now = datetime.now(UTC)
    artifact = OptimizationArtifact(
        project_id=project_id,
        cycle_id=item.cycle_id,
        work_item_id=item.id,
        kind=req.kind,
        title={
            "content": f"基于证据的内容草稿 · {item.title}",
            "instructions": f"基于证据的执行说明 · {item.title}",
            "jsonld": f"基于证据的 JSON-LD · {item.title}",
        }[req.kind],
        version=max((existing.version for existing in previous), default=0) + 1,
        content=content,
        structured_content=structured_content,
        source_snapshot={
            **evidence,
            "brief_version": project.brief_version,
            "brand_fact_ids": [fact.id for fact in facts],
            "generation_engine": req.engine_id,
            "generated_at": now.isoformat(),
        },
        created_by="assistant",
    )
    activity = ProjectActivity(
        project_id=project_id,
        cycle_id=item.cycle_id,
        kind="optimization",
        title=f"生成{artifact.title}",
        status=RunStatus.done,
        input_snapshot={
            "work_item_id": item.id,
            "artifact_kind": req.kind,
            "generation_engine": req.engine_id,
            "brand_fact_ids": [fact.id for fact in facts],
        },
        output_summary={"artifact_id": artifact.id, "version": artifact.version},
        finished_at=now,
    )
    item.status = "review"
    item.execution_mode = "self" if item.execution_mode == "unassigned" else item.execution_mode
    item.updated_at = now
    session.add(item)
    session.add(artifact)
    session.add(activity)
    session.commit()
    session.refresh(artifact)
    return _artifact_dto(artifact)
