"""项目编排：创建/列出项目（自动补 default org + client）。"""

from __future__ import annotations

import json
from calendar import monthrange
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import update
from sqlmodel import Session, col, select

from keeplix.engines.prompt_quality import classify_prompt, summarize_prompt_quality
from keeplix.models import (
    BrandEntity,
    BrandFact,
    CitationResult,
    CitationRun,
    Client,
    CycleRetestPlan,
    DeliveryRecord,
    GeoCycle,
    OptimizationArtifact,
    Organization,
    Project,
    ProjectActivity,
    Prompt,
    PromptSet,
    TrackingPlan,
    VisibilityScore,
    WorkItem,
)
from keeplix.models.enums import Severity
from keeplix.schemas import (
    ArtifactExportResponse,
    ArtifactRevisionCreate,
    ArtifactStatusUpdate,
    CitationEvidence,
    CitationRunRequest,
    CycleRetestPlanDTO,
    CycleVerificationResponse,
    DeliveryRecordCreate,
    DeliveryRecordDTO,
    DiagnosisSummary,
    DueRetestResponse,
    DueTrackingResponse,
    GeoCycleDTO,
    OptimizationArtifactDTO,
    ProjectActivityDTO,
    ProjectCreate,
    ProjectDashboard,
    ProjectResponse,
    ProjectUpdate,
    PromptSetCreate,
    PromptSetResponse,
    PromptSetVersionCreate,
    SoVEngineResult,
    TrackingExecutionResponse,
    TrackingPlanCreate,
    TrackingPlanResponse,
    VisibilityDiagnosis,
    VisibilitySnapshot,
    WorkItemDetail,
    WorkItemDTO,
    WorkItemUpdate,
)
from keeplix.services.agent_service import get_agent_policy, list_agent_runs
from keeplix.services.citation_service import run_citations
from keeplix.services.research_scope_service import (
    incomplete_brief_message,
    research_brief_missing_fields,
)

_DEFAULT_ORG = "keeplix-default-org"
_TRACKING_LEASE_DURATION = timedelta(minutes=30)
_TRACKING_RETRY_BASE = timedelta(minutes=5)
_TRACKING_RETRY_MAX = timedelta(hours=6)


def _claim_tracking_plan(
    plan_id: str,
    session: Session,
    *,
    now: datetime,
    due_only: bool,
) -> str | None:
    token = str(uuid4())
    conditions = [
        col(TrackingPlan.id) == plan_id,
        col(TrackingPlan.status) == "active",
        col(TrackingPlan.lease_expires_at).is_(None)
        | (col(TrackingPlan.lease_expires_at) <= now),
    ]
    if due_only:
        conditions.extend(
            [
                col(TrackingPlan.cadence) != "manual",
                col(TrackingPlan.next_run_at).is_(None)
                | (col(TrackingPlan.next_run_at) <= now),
            ]
        )
    result = session.execute(
        update(TrackingPlan)
        .where(*conditions)
        .values(
            lease_token=token,
            lease_expires_at=now + _TRACKING_LEASE_DURATION,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    session.expire_all()
    return token if getattr(result, "rowcount", 0) == 1 else None


def _release_tracking_plan(plan_id: str, token: str, session: Session) -> None:
    session.execute(
        update(TrackingPlan)
        .where(
            col(TrackingPlan.id) == plan_id,
            col(TrackingPlan.lease_token) == token,
        )
        .values(lease_token=None, lease_expires_at=None)
        .execution_options(synchronize_session=False)
    )
    session.commit()
    session.expire_all()


def _failure_retry_at(now: datetime, cadence: str, failures: int) -> datetime | None:
    cadence_run_at = _next_run_at(now, cadence)
    if cadence_run_at is None:
        return None
    multiplier = 2 ** max(failures - 1, 0)
    retry_delay = min(_TRACKING_RETRY_BASE * multiplier, _TRACKING_RETRY_MAX)
    return min(cadence_run_at, now + retry_delay)


def _record_tracking_plan_failure(
    plan_id: str,
    error: Exception,
    session: Session,
    *,
    now: datetime,
) -> TrackingExecutionResponse:
    plan = session.get(TrackingPlan, plan_id)
    if plan is None:
        raise ValueError("追踪计划不存在") from error
    error_message = str(error).strip() or type(error).__name__
    plan.last_run_at = now
    plan.last_error = error_message[:800]
    plan.consecutive_failures += 1
    plan.next_run_at = _failure_retry_at(now, plan.cadence, plan.consecutive_failures)
    plan.lease_token = None
    plan.lease_expires_at = None
    plan.updated_at = now
    session.add(plan)
    session.commit()
    return TrackingExecutionResponse(
        plan_id=plan.id,
        status="failed",
        results=[],
        errors={"plan": error_message},
        last_run_at=now,
        next_run_at=plan.next_run_at,
    )


def _diagnose_visibility(project_id: str, session: Session) -> DiagnosisSummary:
    """Summarise *qualified* answer evidence into reviewable gaps.

    This deliberately does not create WorkItems. A diagnosis tells the user what
    happened in a specific answer surface and links the evidence; deciding how to
    improve it remains a separate, approved Phase 2 action.
    """
    project = session.get(Project, project_id)
    if project is None:
        return DiagnosisSummary(warnings=["项目不存在。"])
    rows = session.exec(
        select(CitationResult, CitationRun)
        .join(CitationRun, col(CitationResult.citation_run_id) == col(CitationRun.id))
        .where(
            CitationRun.project_id == project_id,
            CitationRun.brief_version == project.brief_version,
            CitationRun.report_eligible,
            CitationRun.status == "done",
        )
        .order_by(col(CitationRun.started_at).desc())
    ).all()
    if not rows:
        return DiagnosisSummary(
            warnings=["尚无可用于正式诊断的真实答案面样本；请先完成一次已认证答案面的检测。"],
        )

    groups: dict[tuple[str, str, str], dict] = {}
    run_ids: set[str] = set()
    coverage_statuses: list[str] = []
    for result, run in rows:
        run_ids.add(run.id)
        quality = run.measurement_quality or {}
        coverage_statuses.append(str(quality.get("status", "limited")))
        intents = {
            str(item.get("text")): str(item.get("intent", "category"))
            for item in quality.get("prompt_intents", [])
            if isinstance(item, dict)
        }
        intent = intents.get(result.prompt_text, "category")
        key = (run.engine_id, result.prompt_text, intent)
        group = groups.setdefault(
            key,
            {
                "samples": 0,
                "brand": 0,
                "own": 0,
                "competitors": {},
                "urls": [],
                "runs": set(),
            },
        )
        group["samples"] += 1
        group["brand"] += int(result.brand_mentioned)
        group["own"] += int(result.own_domain_cited)
        group["urls"].extend(result.cited_urls or [])
        group["runs"].add(run.id)
        for competitor in result.competitor_mentions or []:
            group["competitors"][competitor] = group["competitors"].get(competitor, 0) + 1

    insights: list[VisibilityDiagnosis] = []
    for (engine_id, prompt_text, intent), group in groups.items():
        competitors = group["competitors"]
        samples = group["samples"]
        if group["brand"] == 0 and competitors:
            mentioned = "、".join(sorted(competitors))
            kind, priority = "competitor_gap", "high"
            title = "竞品已进入答案，品牌尚未出现"
            detail = (
                f"在「{prompt_text}」的 {samples} 个 {engine_id} 正式样本中，"
                f"品牌未被提及；{mentioned} 被提及。先查看原始回答与来源，"
                "再决定是否建立优化工作。"
            )
        elif group["brand"] > 0 and group["own"] == 0:
            kind, priority = "citation_gap", "medium"
            title = "品牌被提及，但未引用自有域名"
            detail = (
                f"在「{prompt_text}」的 {samples} 个 {engine_id} 正式样本中，"
                f"品牌出现 {group['brand']} 次，但自有域名没有作为答案来源出现。"
            )
        elif group["brand"] == 0:
            kind, priority = "visibility_gap", "medium"
            title = "当前问题下尚未进入答案"
            detail = (
                f"在「{prompt_text}」的 {samples} 个 {engine_id} 正式样本中，"
                "未检测到品牌提及；这只说明当前问题和答案面，不代表整个市场。"
            )
        else:
            continue
        insight_id = f"{engine_id}:{intent}:{prompt_text}".replace(" ", "-")
        insights.append(
            VisibilityDiagnosis(
                id=insight_id,
                priority=priority,
                kind=kind,
                title=title,
                detail=detail,
                engine_id=engine_id,
                prompt_text=prompt_text,
                prompt_intent=intent,
                sample_size=samples,
                brand_mentions=group["brand"],
                own_domain_citations=group["own"],
                competitor_mentions=competitors,
                cited_urls=list(dict.fromkeys(group["urls"]))[:12],
                evidence_run_ids=sorted(group["runs"]),
            )
        )
    rank = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda item: (rank[item.priority], item.engine_id, item.prompt_text))
    coverage_status = (
        "comprehensive" if "comprehensive" in coverage_statuses else
        "balanced" if "balanced" in coverage_statuses else "limited"
    )
    warnings = []
    if coverage_status != "comprehensive":
        warnings.append("问题集覆盖尚不完整；诊断只适用于已测问题范围，不能作为完整市场结论。")
    if len(rows) < 8:
        warnings.append("正式样本数量较少；建议按同一问题集持续追踪后再判断趋势。")
    return DiagnosisSummary(
        qualified_sample_count=len(rows),
        qualified_run_count=len(run_ids),
        coverage_status=coverage_status,
        warnings=warnings,
        insights=insights,
    )


def _ensure_default_org(session: Session) -> Organization:
    org = session.get(Organization, _DEFAULT_ORG)
    if org is None:
        org = Organization(id=_DEFAULT_ORG, name="keeplix")
        session.add(org)
        session.flush()
    return org


def create_project(req: ProjectCreate, session: Session) -> ProjectResponse:
    org = _ensure_default_org(session)

    client = session.exec(
        select(Client).where(Client.org_id == org.id, Client.name == req.client_name)
    ).first()
    if client is None:
        client = Client(org_id=org.id, name=req.client_name)
        session.add(client)
        session.flush()

    project = Project(
        client_id=client.id,
        name=req.name,
        primary_domain=req.primary_domain,
        locale=req.locale,
        market=req.market,
        category=req.category,
        research_objective=req.research_objective,
    )
    session.add(project)
    session.flush()
    session.add(
        BrandEntity(
            project_id=project.id,
            brand_name=req.brand_name.strip() or req.name,
            domains=[req.primary_domain] if req.primary_domain else [],
            competitors=list(dict.fromkeys(req.competitors)),
        )
    )
    session.commit()
    session.refresh(project)
    return _project_response(project, session)


def _project_response(project: Project, session: Session) -> ProjectResponse:
    client = session.get(Client, project.client_id)
    brand = session.exec(
        select(BrandEntity).where(BrandEntity.project_id == project.id)
    ).first()
    missing_fields = research_brief_missing_fields(project, brand)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        client_name=client.name if client else "default",
        brand_name=brand.brand_name if brand else project.name,
        competitors=brand.competitors if brand else [],
        primary_domain=project.primary_domain,
        locale=project.locale,
        market=project.market,
        category=project.category,
        research_objective=project.research_objective,
        brief_version=project.brief_version,
        brief_ready=not missing_fields,
        brief_missing_fields=missing_fields,
        status=project.status,
    )


def list_projects(session: Session) -> list[ProjectResponse]:
    projects = session.exec(select(Project)).all()
    return [_project_response(project, session) for project in projects]


def update_project(
    project_id: str,
    req: ProjectUpdate,
    session: Session,
) -> ProjectResponse | None:
    project = session.get(Project, project_id)
    if project is None:
        return None
    brand = session.exec(
        select(BrandEntity).where(BrandEntity.project_id == project_id)
    ).first()
    if brand is None:
        brand = BrandEntity(project_id=project_id, brand_name=project.name)

    normalized_competitors = (
        list(dict.fromkeys(name.strip() for name in req.competitors if name.strip()))
        if req.competitors is not None
        else brand.competitors
    )
    requested_scope = (
        req.brand_name.strip() if req.brand_name is not None else brand.brand_name,
        req.primary_domain.strip() if req.primary_domain is not None else project.primary_domain,
        req.market.strip() if req.market is not None else project.market,
        req.category.strip() if req.category is not None else project.category,
        req.research_objective.strip()
        if req.research_objective is not None
        else project.research_objective,
        normalized_competitors,
    )
    current_scope = (
        brand.brand_name,
        project.primary_domain,
        project.market,
        project.category,
        project.research_objective,
        brand.competitors,
    )
    scope_changed = requested_scope != current_scope

    if req.primary_domain is not None:
        project.primary_domain = req.primary_domain.strip()
        brand.domains = [project.primary_domain] if project.primary_domain else []
    if req.market is not None:
        project.market = req.market.strip()
    if req.category is not None:
        project.category = req.category.strip()
    if req.research_objective is not None:
        project.research_objective = req.research_objective.strip()
    if req.brand_name is not None:
        brand.brand_name = req.brand_name.strip()
    if req.competitors is not None:
        brand.competitors = normalized_competitors

    if scope_changed:
        project.brief_version += 1
        plans = session.exec(
            select(TrackingPlan).where(
                TrackingPlan.project_id == project_id,
                TrackingPlan.status == "active",
            )
        ).all()
        for plan in plans:
            prompt_set = session.get(PromptSet, plan.prompt_set_id)
            if prompt_set is not None and prompt_set.brief_version < project.brief_version:
                plan.status = "paused"
                plan.next_run_at = None
                plan.last_error = "研究 Brief 已更新；请基于当前范围建立新问题集和追踪计划。"
                plan.updated_at = datetime.now(UTC)
                session.add(plan)

    session.add(project)
    session.add(brand)
    session.commit()
    session.refresh(project)
    return _project_response(project, session)


def create_prompt_set(
    project_id: str,
    req: PromptSetCreate,
    session: Session,
) -> PromptSetResponse:
    return _create_prompt_set(project_id, req.name, req.prompts, req.kind, session)


def create_prompt_set_version(
    project_id: str,
    prompt_set_id: str,
    req: PromptSetVersionCreate,
    session: Session,
) -> PromptSetResponse:
    source = session.get(PromptSet, prompt_set_id)
    if source is None or source.project_id != project_id:
        raise ValueError("问题集不存在")
    return _create_prompt_set(
        project_id,
        req.name or source.name,
        req.prompts,
        source.kind,
        session,
        source_prompt_set_id=source.id,
    )


def _create_prompt_set(
    project_id: str,
    name: str,
    raw_prompts: list[str],
    kind: str,
    session: Session,
    *,
    source_prompt_set_id: str | None = None,
) -> PromptSetResponse:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError("项目不存在")
    brand = session.exec(select(BrandEntity).where(BrandEntity.project_id == project_id)).first()
    missing_fields = research_brief_missing_fields(project, brand)
    if missing_fields:
        raise ValueError(incomplete_brief_message(missing_fields))
    brand_name = brand.brand_name if brand else project.name
    aliases = brand.aliases if brand else []
    previous = session.exec(
        select(PromptSet).where(PromptSet.project_id == project_id, PromptSet.name == name)
    ).all()
    prompt_set = PromptSet(
        project_id=project_id,
        source_prompt_set_id=source_prompt_set_id,
        name=name,
        version=len(previous) + 1,
        kind=kind,
        brief_version=project.brief_version,
    )
    session.add(prompt_set)
    session.flush()
    prompts = list(dict.fromkeys(text.strip() for text in raw_prompts if text.strip()))
    if not prompts:
        raise ValueError("问题集至少需要一个有效问题")
    prompt_rows = []
    for text in prompts:
        prompt = Prompt(
            project_id=project_id,
            prompt_set_id=prompt_set.id,
            text=text,
            intent=classify_prompt(text, brand_name, aliases),
        )
        prompt_rows.append(prompt)
        session.add(prompt)
    for existing in previous:
        existing.active = False
        session.add(existing)
    session.commit()
    return PromptSetResponse(
        id=prompt_set.id,
        source_prompt_set_id=prompt_set.source_prompt_set_id,
        name=prompt_set.name,
        version=prompt_set.version,
        kind=prompt_set.kind,
        active=prompt_set.active,
        brief_version=prompt_set.brief_version,
        scope_current=prompt_set.brief_version == project.brief_version,
        prompts=prompts,
        prompt_items=[
            {"id": prompt.id, "text": prompt.text, "intent": prompt.intent.value}
            for prompt in prompt_rows
        ],
        measurement_quality=summarize_prompt_quality(prompts, brand_name, aliases),
        created_at=prompt_set.created_at,
    )


def list_prompt_sets(project_id: str, session: Session) -> list[PromptSetResponse]:
    sets = session.exec(
        select(PromptSet)
        .where(PromptSet.project_id == project_id)
        .order_by(col(PromptSet.created_at).desc())
    ).all()
    project = session.get(Project, project_id)
    brand = session.exec(select(BrandEntity).where(BrandEntity.project_id == project_id)).first()
    brand_name = brand.brand_name if brand else project.name if project else ""
    aliases = brand.aliases if brand else []
    responses = []
    for prompt_set in sets:
        prompt_rows = session.exec(
            select(Prompt).where(Prompt.prompt_set_id == prompt_set.id)
        ).all()
        prompts = [prompt.text for prompt in prompt_rows]
        responses.append(
            PromptSetResponse(
                id=prompt_set.id,
                source_prompt_set_id=prompt_set.source_prompt_set_id,
                name=prompt_set.name,
                version=prompt_set.version,
                kind=prompt_set.kind,
                active=prompt_set.active,
                brief_version=prompt_set.brief_version,
                scope_current=bool(project and prompt_set.brief_version == project.brief_version),
                prompts=prompts,
                prompt_items=[
                    {"id": prompt.id, "text": prompt.text, "intent": prompt.intent.value}
                    for prompt in prompt_rows
                ],
                measurement_quality=summarize_prompt_quality(prompts, brand_name, aliases),
                created_at=prompt_set.created_at,
            )
        )
    return responses


def create_tracking_plan(
    project_id: str,
    req: TrackingPlanCreate,
    session: Session,
) -> TrackingPlanResponse:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError("项目不存在")
    brand = session.exec(
        select(BrandEntity).where(BrandEntity.project_id == project_id)
    ).first()
    missing_fields = research_brief_missing_fields(project, brand)
    if missing_fields:
        raise ValueError(incomplete_brief_message(missing_fields))
    prompt_set = session.get(PromptSet, req.prompt_set_id)
    if prompt_set is None or prompt_set.project_id != project_id:
        raise ValueError("问题集不存在")
    if not prompt_set.active:
        raise ValueError("该问题集已被新版本替代，请使用当前版本创建追踪计划")
    if prompt_set.brief_version != project.brief_version:
        raise ValueError("该问题集属于旧研究 Brief，请先基于当前范围创建新问题集")

    plan = TrackingPlan(
        project_id=project_id,
        prompt_set_id=req.prompt_set_id,
        engine_ids=req.engine_ids,
        samples=req.samples,
        cadence=req.cadence,
        next_run_at=req.next_run_at or _next_run_at(datetime.now(UTC), req.cadence),
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return _tracking_plan_response(plan, prompt_set, session)


def list_tracking_plans(project_id: str, session: Session) -> list[TrackingPlanResponse]:
    plans = session.exec(
        select(TrackingPlan)
        .where(TrackingPlan.project_id == project_id)
        .order_by(col(TrackingPlan.created_at).desc())
    ).all()
    return [
        _tracking_plan_response(plan, session.get(PromptSet, plan.prompt_set_id), session)
        for plan in plans
    ]


def _tracking_plan_response(
    plan: TrackingPlan,
    prompt_set: PromptSet | None,
    session: Session,
) -> TrackingPlanResponse:
    prompt_rows = session.exec(
        select(Prompt).where(Prompt.prompt_set_id == plan.prompt_set_id)
    ).all()
    prompts = [prompt.text for prompt in prompt_rows]
    project = session.get(Project, plan.project_id)
    brand = session.exec(
        select(BrandEntity).where(BrandEntity.project_id == plan.project_id)
    ).first()
    brand_name = brand.brand_name if brand else project.name if project else ""
    aliases = brand.aliases if brand else []
    return TrackingPlanResponse(
        id=plan.id,
        prompt_set_id=plan.prompt_set_id,
        prompt_set_name=prompt_set.name if prompt_set else "已删除的问题集",
        question_count=len(prompt_rows),
        prompt_items=[
            {"id": prompt.id, "text": prompt.text, "intent": prompt.intent.value}
            for prompt in prompt_rows
        ],
        measurement_quality=summarize_prompt_quality(prompts, brand_name, aliases),
        engine_ids=plan.engine_ids,
        samples=plan.samples,
        cadence=plan.cadence,
        status=plan.status,
        scope_current=bool(
            project and prompt_set and prompt_set.brief_version == project.brief_version
        ),
        next_run_at=plan.next_run_at,
        last_run_at=plan.last_run_at,
        last_error=plan.last_error,
        consecutive_failures=plan.consecutive_failures,
        created_at=plan.created_at,
    )


def _next_run_at(base: datetime, cadence: str) -> datetime | None:
    if cadence == "manual":
        return None
    if cadence == "daily":
        return base + timedelta(days=1)
    if cadence == "weekly":
        return base + timedelta(days=7)
    if cadence == "monthly":
        year = base.year + (1 if base.month == 12 else 0)
        month = 1 if base.month == 12 else base.month + 1
        day = min(base.day, monthrange(year, month)[1])
        return base.replace(year=year, month=month, day=day)
    raise ValueError("不支持的追踪频率")


async def execute_tracking_plan(
    project_id: str,
    plan_id: str,
    session: Session,
    *,
    triggered_by: str = "user",
    lease_token: str | None = None,
) -> TrackingExecutionResponse:
    plan = session.get(TrackingPlan, plan_id)
    if plan is None or plan.project_id != project_id:
        raise ValueError("追踪计划不存在")
    if plan.status != "active":
        raise ValueError("追踪计划已暂停")
    project = session.get(Project, project_id)
    prompt_set = session.get(PromptSet, plan.prompt_set_id)
    if project is None or prompt_set is None:
        raise ValueError("追踪计划的项目或问题集不存在")
    brand = session.exec(
        select(BrandEntity).where(BrandEntity.project_id == project_id)
    ).first()
    missing_fields = research_brief_missing_fields(project, brand)
    if missing_fields:
        raise ValueError(incomplete_brief_message(missing_fields))
    if prompt_set.brief_version != project.brief_version:
        raise ValueError("追踪计划属于旧研究 Brief，请基于当前范围建立新计划")
    prompts = [
        prompt.text
        for prompt in session.exec(
            select(Prompt).where(Prompt.prompt_set_id == plan.prompt_set_id, Prompt.active)
        ).all()
    ]
    if not prompts:
        raise ValueError("追踪计划没有可用问题")
    brand_name = brand.brand_name if brand else project.name
    aliases = brand.aliases if brand else []
    domains = (
        brand.domains if brand else ([project.primary_domain] if project.primary_domain else [])
    )

    execution_token = lease_token
    if execution_token is None:
        execution_token = _claim_tracking_plan(
            plan.id,
            session,
            now=datetime.now(UTC),
            due_only=False,
        )
        if execution_token is None:
            raise ValueError("追踪计划正在执行，请稍后重试")
    else:
        session.expire_all()
        claimed_plan = session.get(TrackingPlan, plan.id)
        if claimed_plan is None or claimed_plan.lease_token != execution_token:
            raise ValueError("追踪计划执行租约已失效")
        plan = claimed_plan

    try:
        results: list[SoVEngineResult] = []
        errors: dict[str, str] = {}
        for engine_id in plan.engine_ids:
            try:
                response = await run_citations(
                    CitationRunRequest(
                        project_id=project_id,
                        prompt_set_id=plan.prompt_set_id,
                        tracking_plan_id=plan.id,
                        triggered_by=triggered_by,
                        engine_ids=[engine_id],
                        prompts=prompts,
                        brand_name=brand_name,
                        aliases=aliases,
                        brand_domains=domains,
                        competitors=brand.competitors if brand else [],
                        samples=plan.samples,
                    ),
                    session,
                )
                results.extend(response.results)
                errors.update(response.errors)
            except Exception as error:  # each engine is isolated; the next one must still run
                errors[engine_id] = type(error).__name__

        now = datetime.now(UTC)
        status = "done" if not errors else "partial" if results else "failed"
        plan.last_run_at = now
        plan.last_error = (
            ", ".join(f"{engine}: {error}" for engine, error in errors.items()) or None
        )
        plan.consecutive_failures = plan.consecutive_failures + 1 if errors else 0
        plan.next_run_at = (
            _failure_retry_at(now, plan.cadence, plan.consecutive_failures)
            if status == "failed"
            else _next_run_at(now, plan.cadence)
        )
        plan.updated_at = now
        session.add(plan)
        session.commit()
        if any(result.report_eligible for result in results):
            from keeplix.services.agent_service import maybe_plan_from_tracking

            active_cycle = session.exec(
                select(GeoCycle).where(
                    GeoCycle.project_id == project_id,
                    GeoCycle.status == "active",
                )
            ).first()
            if active_cycle:
                maybe_plan_from_tracking(project_id, active_cycle.id, session)
        return TrackingExecutionResponse(
            plan_id=plan.id,
            status=status,
            results=results,
            errors=errors,
            last_run_at=now,
            next_run_at=plan.next_run_at,
        )
    finally:
        _release_tracking_plan(plan.id, execution_token, session)


async def run_due_tracking_plans(session: Session) -> DueTrackingResponse:
    now = datetime.now(UTC)
    plans = session.exec(
        select(TrackingPlan).where(
            TrackingPlan.status == "active",
            TrackingPlan.cadence != "manual",
            col(TrackingPlan.next_run_at).is_(None) | (col(TrackingPlan.next_run_at) <= now),
            col(TrackingPlan.lease_expires_at).is_(None)
            | (col(TrackingPlan.lease_expires_at) <= now),
        )
    ).all()
    executions: list[TrackingExecutionResponse] = []
    for plan in plans:
        token = _claim_tracking_plan(
            plan.id,
            session,
            now=now,
            due_only=True,
        )
        if token is None:
            continue
        try:
            executions.append(
                await execute_tracking_plan(
                    plan.project_id,
                    plan.id,
                    session,
                    triggered_by="schedule",
                    lease_token=token,
                )
            )
        except Exception as error:
            executions.append(
                _record_tracking_plan_failure(
                    plan.id,
                    error,
                    session,
                    now=datetime.now(UTC),
                )
            )
    return DueTrackingResponse(checked_at=now, executions=executions)


def _visibility_comparisons(scores: Sequence[VisibilityScore]) -> dict[str, dict]:
    """Describe whether each formal snapshot can support a trend claim.

    A tracking plan freezes its prompt set, engines and sample target. We still
    require the observed answer surface, acquisition path and measurement scope
    to match, because changing any of those creates a new measurement baseline.
    Ad-hoc runs remain useful current evidence but never become a trend series.
    """
    grouped: dict[tuple[str, str, int], list[VisibilityScore]] = {}
    comparisons: dict[str, dict] = {}
    for score in scores:
        if score.tracking_plan_id is None:
            comparisons[score.id] = {
                "comparison_status": "standalone",
                "comparison_note": "单次检测未绑定追踪计划，不计算趋势。",
            }
            continue
        grouped.setdefault(
            (score.tracking_plan_id, score.engine_id, score.brief_version), []
        ).append(score)

    for values in grouped.values():
        ordered = sorted(values, key=lambda item: item.period)
        for index, score in enumerate(ordered):
            if index == 0:
                comparisons[score.id] = {
                    "comparison_status": "baseline",
                    "comparison_note": "这是该追踪范围在此答案面的首次正式基线。",
                }
                continue
            previous = ordered[index - 1]
            current_scope = (
                score.surface_name,
                score.provider_acquisition,
                score.measurement_scope,
            )
            previous_scope = (
                previous.surface_name,
                previous.provider_acquisition,
                previous.measurement_scope,
            )
            if current_scope != previous_scope:
                comparisons[score.id] = {
                    "comparison_status": "scope_changed",
                    "comparison_note": "答案面或采集范围发生变化，本次结果作为新基线，不计算升降。",
                    "previous_period": previous.period,
                }
                continue
            note = "问题集、答案面和采集范围一致，可与上次正式结果比较。"
            if score.sample_size != previous.sample_size:
                note += " 两次有效样本量不同，解读时应同时参考置信区间。"
            comparisons[score.id] = {
                "comparison_status": "comparable",
                "comparison_note": note,
                "previous_period": previous.period,
                "entity_delta": score.entity_sov - previous.entity_sov,
                "citation_delta": score.citation_sov - previous.citation_sov,
            }
    return comparisons


def get_project_dashboard(project_id: str, session: Session) -> ProjectDashboard | None:
    project = session.get(Project, project_id)
    if project is None:
        return None

    scores = session.exec(
        select(VisibilityScore)
        .where(
            VisibilityScore.project_id == project_id,
            VisibilityScore.report_eligible,
        )
        .order_by(col(VisibilityScore.period).desc())
        .limit(24)
    ).all()
    comparison_by_score = _visibility_comparisons(scores)
    run_count = len(
        session.exec(select(CitationRun.id).where(CitationRun.project_id == project_id)).all()
    )
    evidence_rows = session.exec(
        select(CitationResult, CitationRun)
        .join(CitationRun, col(CitationResult.citation_run_id) == col(CitationRun.id))
        .where(CitationRun.project_id == project_id)
        .order_by(col(CitationRun.started_at).desc())
        .limit(30)
    ).all()
    activities = session.exec(
        select(ProjectActivity)
        .where(ProjectActivity.project_id == project_id)
        .order_by(col(ProjectActivity.started_at).desc())
        .limit(50)
    ).all()
    cycles = session.exec(
        select(GeoCycle)
        .where(GeoCycle.project_id == project_id)
        .order_by(col(GeoCycle.started_at).desc())
    ).all()
    retests = session.exec(
        select(CycleRetestPlan)
        .where(CycleRetestPlan.project_id == project_id)
        .order_by(col(CycleRetestPlan.created_at).desc())
    ).all()
    latest_retest_by_cycle: dict[str, CycleRetestPlan] = {}
    for retest in retests:
        latest_retest_by_cycle.setdefault(retest.cycle_id, retest)
    work_items = session.exec(
        select(WorkItem)
        .where(WorkItem.project_id == project_id)
        .order_by(col(WorkItem.created_at).desc())
    ).all()

    project_response = _project_response(project, session)
    return ProjectDashboard(
        **project_response.model_dump(),
        citation_runs=run_count,
        visibility=[
            VisibilitySnapshot(
                engine_id=score.engine_id,
                surface_name=score.surface_name or score.engine_id,
                acquisition=score.provider_acquisition,
                measurement_scope=score.measurement_scope,
                report_eligible=score.report_eligible,
                measurement_quality=score.measurement_quality,
                entity_sov=score.entity_sov,
                citation_sov=score.citation_sov,
                competitor_sov=score.competitor_sov,
                relative_sov=score.relative_sov,
                avg_rank=score.avg_rank,
                sample_size=score.sample_size,
                entity_ci_low=score.entity_ci_low,
                entity_ci_high=score.entity_ci_high,
                citation_ci_low=score.citation_ci_low,
                citation_ci_high=score.citation_ci_high,
                period=score.period,
                tracking_plan_id=score.tracking_plan_id,
                brief_version=score.brief_version,
                scope_current=score.brief_version == project.brief_version,
                **comparison_by_score[score.id],
            )
            for score in scores
        ],
        evidence=[
            CitationEvidence(
                run_id=run.id,
                activity_id=run.activity_id,
                engine_id=run.engine_id,
                captured_at=run.started_at,
                prompt_text=result.prompt_text,
                answer_text=result.answer_text,
                cited_urls=result.cited_urls,
                brand_mentioned=result.brand_mentioned,
                own_domain_cited=result.own_domain_cited,
                competitor_mentions=result.competitor_mentions,
                request_id=(result.provider_metadata or {}).get("request_id"),
                provider_metadata=result.provider_metadata or {},
                surface_name=run.surface_name,
                measurement_scope=run.measurement_scope,
                report_eligible=run.report_eligible,
                brief_version=run.brief_version,
                scope_current=run.brief_version == project.brief_version,
            )
            for result, run in evidence_rows
        ],
        diagnosis=_diagnose_visibility(project_id, session),
        prompt_sets=list_prompt_sets(project_id, session),
        tracking_plans=list_tracking_plans(project_id, session),
        cycles=[
            GeoCycleDTO(
                id=cycle.id,
                name=cycle.name,
                objective=cycle.objective,
                stage=cycle.stage,
                status=cycle.status,
                measurement_config=cycle.measurement_config or {},
                baseline_summary=cycle.baseline_summary or {},
                verification_summary=cycle.verification_summary or {},
                retest_plan=(
                    _retest_dto(latest_retest_by_cycle[cycle.id])
                    if cycle.id in latest_retest_by_cycle
                    else None
                ),
                started_at=cycle.started_at,
                completed_at=cycle.completed_at,
            )
            for cycle in cycles
        ],
        work_items=[_work_item_dto(item) for item in work_items],
        agent_policy=get_agent_policy(project_id, session),
        agent_runs=list_agent_runs(project_id, session),
        activities=[
            ProjectActivityDTO(
                id=activity.id,
                kind=activity.kind,
                title=activity.title,
                triggered_by=activity.triggered_by,
                status=activity.status,
                input_snapshot=activity.input_snapshot,
                output_summary=activity.output_summary,
                started_at=activity.started_at,
                finished_at=activity.finished_at,
            )
            for activity in activities
        ],
    )


def update_work_item(
    project_id: str,
    work_item_id: str,
    req: WorkItemUpdate,
    session: Session,
) -> WorkItemDTO:
    item = session.get(WorkItem, work_item_id)
    if item is None or item.project_id != project_id:
        raise ValueError("优化工作不存在")
    if req.status is not None:
        allowed_statuses = {"open", "in_progress", "review", "done", "dismissed"}
        if req.status not in allowed_statuses:
            raise ValueError("不支持的工作状态")
        if req.status == "done":
            artifacts = session.exec(
                select(OptimizationArtifact).where(
                    OptimizationArtifact.work_item_id == item.id,
                    OptimizationArtifact.status != "superseded",
                )
            ).all()
            if not artifacts or any(artifact.status != "implemented" for artifact in artifacts):
                raise ValueError("工作只能在所有审批产物完成实施记录后结束")
        item.status = req.status
        item.completed_at = datetime.now(UTC) if req.status == "done" else None
    if req.execution_mode is not None:
        allowed_modes = {"unassigned", "self", "team", "agent"}
        if req.execution_mode not in allowed_modes:
            raise ValueError("不支持的执行方式")
        item.execution_mode = req.execution_mode
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)
    return _work_item_dto(item)


def _work_item_dto(item: WorkItem) -> WorkItemDTO:
    return WorkItemDTO(
        id=item.id,
        cycle_id=item.cycle_id,
        source_activity_id=item.source_activity_id,
        title=item.title,
        detail=item.detail,
        category=item.category,
        priority=item.priority,
        status=item.status,
        execution_mode=item.execution_mode,
        evidence_snapshot=item.evidence_snapshot,
        output_snapshot=item.output_snapshot,
        created_at=item.created_at,
        updated_at=item.updated_at,
        completed_at=item.completed_at,
    )


def create_work_item_from_diagnosis(
    project_id: str,
    diagnosis_id: str,
    session: Session,
) -> WorkItemDTO:
    """Promote one reviewed, qualified diagnostic into a traceable work item."""
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError("项目不存在")
    diagnosis = _diagnose_visibility(project_id, session)
    insight = next((item for item in diagnosis.insights if item.id == diagnosis_id), None)
    if insight is None:
        raise ValueError("该诊断不存在、已过期，或没有正式证据")

    existing = next(
        (
            item
            for item in session.exec(
                select(WorkItem).where(WorkItem.project_id == project_id)
            ).all()
            if (item.evidence_snapshot or {}).get("diagnosis_id") == diagnosis_id
            and item.status != "dismissed"
        ),
        None,
    )
    if existing:
        return _work_item_dto(existing)

    runs = [session.get(CitationRun, run_id) for run_id in insight.evidence_run_ids]
    qualified_runs = [run for run in runs if run is not None]
    if not qualified_runs:
        raise ValueError("诊断证据已不可用，请重新检测")
    latest_run = max(qualified_runs, key=lambda run: run.started_at)
    cycle = session.exec(
        select(GeoCycle)
        .where(GeoCycle.project_id == project_id, GeoCycle.status == "active")
        .order_by(col(GeoCycle.started_at).desc())
    ).first()
    if cycle is None:
        brand = session.exec(
            select(BrandEntity).where(BrandEntity.project_id == project_id)
        ).first()
        cycle = GeoCycle(
            project_id=project_id,
            name=f"证据优化周期 {datetime.now(UTC).strftime('%Y-%m-%d')}",
            objective=f"改善「{insight.prompt_text}」在 {insight.engine_id} 答案面中的可见度与引用",
            stage="improve",
            measurement_config={
                "brief_version": latest_run.brief_version,
                "questions": [insight.prompt_text],
                "engine_ids": [insight.engine_id],
                "samples": latest_run.samples,
                "brand_name": brand.brand_name if brand else project.name,
                "aliases": brand.aliases if brand else [],
                "brand_domains": (
                    brand.domains
                    if brand
                    else ([project.primary_domain] if project.primary_domain else [])
                ),
                "competitors": brand.competitors if brand else [],
            },
            baseline_summary={
                "captured_at": (latest_run.finished_at or latest_run.started_at).isoformat(),
                "engines": [
                    {
                        "engine_id": insight.engine_id,
                        "report_eligible": latest_run.report_eligible,
                        "measurement_scope": latest_run.measurement_scope,
                        "source_surface": latest_run.surface_name,
                        "acquisition": latest_run.provider_acquisition,
                        "sample_size": insight.sample_size,
                        "entity_sov": insight.brand_mentions / insight.sample_size,
                        "citation_sov": insight.own_domain_citations / insight.sample_size,
                        "competitor_mentions": insight.competitor_mentions,
                        "source_run_ids": insight.evidence_run_ids,
                    }
                ],
            },
        )
        session.add(cycle)
        session.flush()

    item = WorkItem(
        project_id=project_id,
        cycle_id=cycle.id,
        source_activity_id=latest_run.activity_id,
        title=f"{insight.title}：{insight.prompt_text}",
        detail=insight.detail,
        category={"citation_gap": "citation", "competitor_gap": "competitive"}.get(
            insight.kind, "visibility"
        ),
        priority=Severity(insight.priority),
        evidence_snapshot={
            "diagnosis_id": insight.id,
            "brief_version": latest_run.brief_version,
            "diagnosis_kind": insight.kind,
            "engine_id": insight.engine_id,
            "prompt_text": insight.prompt_text,
            "prompt_intent": insight.prompt_intent,
            "sample_size": insight.sample_size,
            "brand_mentions": insight.brand_mentions,
            "own_domain_citations": insight.own_domain_citations,
            "competitor_mentions": insight.competitor_mentions,
            "cited_urls": insight.cited_urls,
            "citation_run_ids": insight.evidence_run_ids,
        },
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return _work_item_dto(item)


def _artifact_dto(artifact: OptimizationArtifact) -> OptimizationArtifactDTO:
    return OptimizationArtifactDTO(
        id=artifact.id,
        work_item_id=artifact.work_item_id,
        kind=artifact.kind,
        title=artifact.title,
        version=artifact.version,
        status=artifact.status,
        content=artifact.content,
        structured_content=artifact.structured_content,
        source_snapshot=artifact.source_snapshot,
        created_by=artifact.created_by,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
        approved_at=artifact.approved_at,
        implemented_at=artifact.implemented_at,
    )


def _delivery_dto(delivery: DeliveryRecord) -> DeliveryRecordDTO:
    return DeliveryRecordDTO(
        id=delivery.id,
        artifact_id=delivery.artifact_id,
        work_item_id=delivery.work_item_id,
        method=delivery.method,
        status=delivery.status,
        target_url=delivery.target_url,
        notes=delivery.notes,
        created_by=delivery.created_by,
        created_at=delivery.created_at,
        published_at=delivery.published_at,
    )


def _retest_dto(plan: CycleRetestPlan) -> CycleRetestPlanDTO:
    return CycleRetestPlanDTO(
        id=plan.id,
        cycle_id=plan.cycle_id,
        source_delivery_id=plan.source_delivery_id,
        status=plan.status,
        scheduled_for=plan.scheduled_for,
        started_at=plan.started_at,
        completed_at=plan.completed_at,
        last_error=plan.last_error,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _latest_cycle_retest(cycle_id: str, session: Session) -> CycleRetestPlan | None:
    return session.exec(
        select(CycleRetestPlan)
        .where(CycleRetestPlan.cycle_id == cycle_id)
        .order_by(col(CycleRetestPlan.created_at).desc())
    ).first()


def get_work_item_detail(project_id: str, work_item_id: str, session: Session) -> WorkItemDetail:
    item = session.get(WorkItem, work_item_id)
    if item is None or item.project_id != project_id:
        raise ValueError("优化工作不存在")
    artifacts = session.exec(
        select(OptimizationArtifact)
        .where(OptimizationArtifact.work_item_id == item.id)
        .order_by(col(OptimizationArtifact.kind), col(OptimizationArtifact.version).desc())
    ).all()
    deliveries = session.exec(
        select(DeliveryRecord)
        .where(DeliveryRecord.work_item_id == item.id)
        .order_by(col(DeliveryRecord.created_at).desc())
    ).all()
    retest = _latest_cycle_retest(item.cycle_id, session)
    return WorkItemDetail(
        item=_work_item_dto(item),
        artifacts=[_artifact_dto(artifact) for artifact in artifacts],
        deliveries=[_delivery_dto(delivery) for delivery in deliveries],
        retest_plan=_retest_dto(retest) if retest else None,
    )


def create_artifact_revision(
    project_id: str,
    work_item_id: str,
    req: ArtifactRevisionCreate,
    session: Session,
) -> OptimizationArtifactDTO:
    project = session.get(Project, project_id)
    item = session.get(WorkItem, work_item_id)
    if project is None or item is None or item.project_id != project_id:
        raise ValueError("优化工作不存在")
    evidence_version = int((item.evidence_snapshot or {}).get("brief_version", 1))
    if evidence_version != project.brief_version:
        raise ValueError("该优化工作属于旧研究 Brief，请先建立当前基线")
    if req.kind not in {"content", "jsonld", "instructions"}:
        raise ValueError("不支持的产物类型")
    source_artifact = None
    if req.source_artifact_id:
        source_artifact = session.get(OptimizationArtifact, req.source_artifact_id)
        if (
            source_artifact is None
            or source_artifact.project_id != project_id
            or source_artifact.work_item_id != item.id
            or source_artifact.kind != req.kind
        ):
            raise ValueError("来源版本不存在或与当前优化工作不一致")
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
    source_snapshot = {
        **(item.evidence_snapshot or {}),
        **(source_artifact.source_snapshot if source_artifact else {}),
        "brief_version": project.brief_version,
        "revised_from_artifact_id": source_artifact.id if source_artifact else None,
        "revised_at": now.isoformat(),
    }
    artifact = OptimizationArtifact(
        project_id=project_id,
        cycle_id=item.cycle_id,
        work_item_id=item.id,
        kind=req.kind,
        title=req.title,
        version=max((existing.version for existing in previous), default=0) + 1,
        content=req.content,
        structured_content=req.structured_content,
        source_snapshot=source_snapshot,
        created_by="user",
    )
    item.status = "in_progress"
    item.execution_mode = "self" if item.execution_mode == "unassigned" else item.execution_mode
    item.updated_at = now
    session.add(item)
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return _artifact_dto(artifact)


def _validate_artifact_scope(
    project_id: str,
    artifact: OptimizationArtifact,
    session: Session,
) -> None:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError("项目不存在")
    source = artifact.source_snapshot or {}
    evidence_version = int(source.get("brief_version", 1))
    if evidence_version != project.brief_version:
        raise ValueError("该优化产物属于旧研究 Brief，不能审批、导出或实施")
    fact_ids = [fact_id for fact_id in source.get("brand_fact_ids", []) if isinstance(fact_id, str)]
    invalid_fact_ids = [
        fact_id
        for fact_id in fact_ids
        if (
            (fact := session.get(BrandFact, fact_id)) is None
            or fact.project_id != project_id
            or fact.status != "verified"
        )
    ]
    if invalid_fact_ids:
        raise ValueError("该优化产物引用的品牌事实已停用或不可用，请重新生成或修订")


def update_artifact_status(
    project_id: str,
    artifact_id: str,
    req: ArtifactStatusUpdate,
    session: Session,
) -> OptimizationArtifactDTO:
    artifact = session.get(OptimizationArtifact, artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise ValueError("优化产物不存在")
    if req.status != "approved":
        raise ValueError("不支持的产物状态")
    _validate_artifact_scope(project_id, artifact, session)
    now = datetime.now(UTC)
    artifact.status = req.status
    artifact.updated_at = now
    if req.status == "approved":
        artifact.approved_at = now
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return _artifact_dto(artifact)


def _mark_artifact_implemented(
    artifact: OptimizationArtifact, now: datetime, session: Session
) -> None:
    artifact.status = "implemented"
    artifact.implemented_at = now
    artifact.updated_at = now
    session.add(artifact)
    item = session.get(WorkItem, artifact.work_item_id)
    if item is None:
        return
    current_artifacts = session.exec(
        select(OptimizationArtifact).where(
            OptimizationArtifact.work_item_id == item.id,
            OptimizationArtifact.status != "superseded",
        )
    ).all()
    effective_statuses = [
        "implemented" if current.id == artifact.id else current.status
        for current in current_artifacts
    ]
    item.status = (
        "done"
        if effective_statuses and all(status == "implemented" for status in effective_statuses)
        else "in_progress"
    )
    item.completed_at = now if item.status == "done" else None
    item.updated_at = now
    session.add(item)
    if item.status != "done":
        return
    remaining = session.exec(
        select(WorkItem).where(
            WorkItem.cycle_id == item.cycle_id,
            WorkItem.id != item.id,
            col(WorkItem.status).not_in({"done", "dismissed"}),
        )
    ).first()
    if remaining is None:
        cycle = session.get(GeoCycle, item.cycle_id)
        if cycle and cycle.status == "active":
            cycle.stage = "verify"
            session.add(cycle)


def create_delivery_record(
    project_id: str,
    artifact_id: str,
    req: DeliveryRecordCreate,
    session: Session,
) -> DeliveryRecordDTO:
    artifact = session.get(OptimizationArtifact, artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise ValueError("优化产物不存在")
    if artifact.status != "approved":
        raise ValueError("优化产物必须先审批")
    _validate_artifact_scope(project_id, artifact, session)
    if req.method not in {"manual", "cms", "repository"} or req.status != "published":
        raise ValueError("不支持的实施记录")
    if not req.target_url.strip() and not req.notes.strip():
        raise ValueError("请记录实际发布位置或实施说明")
    now = datetime.now(UTC)
    delivery = DeliveryRecord(
        project_id=project_id,
        cycle_id=artifact.cycle_id,
        work_item_id=artifact.work_item_id,
        artifact_id=artifact.id,
        method=req.method,
        status="published",
        target_url=req.target_url.strip(),
        notes=req.notes.strip(),
        published_at=now,
    )
    session.add(delivery)
    _mark_artifact_implemented(artifact, now, session)
    cycle = session.get(GeoCycle, artifact.cycle_id)
    if cycle is not None and cycle.stage == "verify":
        existing_retest = session.exec(
            select(CycleRetestPlan).where(
                CycleRetestPlan.cycle_id == cycle.id,
                col(CycleRetestPlan.status).in_({"scheduled", "running"}),
            )
        ).first()
        if existing_retest is None:
            session.add(
                CycleRetestPlan(
                    project_id=project_id,
                    cycle_id=cycle.id,
                    source_delivery_id=delivery.id,
                    scheduled_for=now + timedelta(days=req.retest_after_days),
                )
            )
    session.commit()
    session.refresh(delivery)
    return _delivery_dto(delivery)


def export_artifact(
    project_id: str,
    artifact_id: str,
    session: Session,
) -> ArtifactExportResponse:
    artifact = session.get(OptimizationArtifact, artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise ValueError("优化产物不存在")
    if artifact.status not in {"approved", "implemented"}:
        raise ValueError("优化产物必须先审批")
    _validate_artifact_scope(project_id, artifact, session)
    is_json = artifact.kind == "jsonld"
    content = (
        json.dumps(artifact.structured_content, ensure_ascii=False, indent=2)
        if is_json
        else artifact.content
    )
    delivery = DeliveryRecord(
        project_id=project_id,
        cycle_id=artifact.cycle_id,
        work_item_id=artifact.work_item_id,
        artifact_id=artifact.id,
        method="export",
        status="exported",
        notes=f"导出 {artifact.title} v{artifact.version}",
    )
    session.add(delivery)
    session.commit()
    session.refresh(delivery)
    filename = f"{artifact.kind}-v{artifact.version}.{'json' if is_json else 'md'}"
    return ArtifactExportResponse(
        filename=filename,
        media_type="application/json" if is_json else "text/markdown",
        content=content,
        delivery=_delivery_dto(delivery),
    )


def _change_assessment(baseline: dict, verification: dict, prefix: str) -> str:
    baseline_value = float(baseline.get(f"{prefix}_sov", 0))
    verification_value = float(verification.get(f"{prefix}_sov", 0))
    baseline_low = baseline.get(f"{prefix}_ci_low")
    baseline_high = baseline.get(f"{prefix}_ci_high")
    verification_low = verification.get(f"{prefix}_ci_low")
    verification_high = verification.get(f"{prefix}_ci_high")
    if (
        baseline_low is not None
        and baseline_high is not None
        and verification_low is not None
        and verification_high is not None
    ):
        if float(verification_low) > float(baseline_high):
            return "improved"
        if float(verification_high) < float(baseline_low):
            return "declined"
    if verification_value == baseline_value:
        return "unchanged"
    return "uncertain"


def _normalized_baseline_scope(baseline: dict, session: Session) -> dict:
    normalized = dict(baseline)
    normalized.setdefault("surface_name", normalized.get("source_surface", ""))
    normalized.setdefault("acquisition", normalized.get("provider_acquisition", ""))
    run_ids = normalized.get("source_run_ids", [])
    source_run = (
        session.get(CitationRun, run_ids[0])
        if isinstance(run_ids, list) and run_ids and isinstance(run_ids[0], str)
        else None
    )
    if source_run is not None:
        normalized["surface_name"] = normalized.get("surface_name") or source_run.surface_name
        normalized["acquisition"] = (
            normalized.get("acquisition") or source_run.provider_acquisition
        )
        normalized["measurement_scope"] = (
            normalized.get("measurement_scope") or source_run.measurement_scope
        )
        normalized["report_eligible"] = normalized.get(
            "report_eligible", source_run.report_eligible
        )
    return normalized


def _comparison_scope_reasons(baseline: dict, verification: dict) -> list[str]:
    reasons: list[str] = []
    fields = (
        ("surface_name", "答案面"),
        ("acquisition", "采集方式"),
        ("measurement_scope", "测量范围"),
    )
    for field, label in fields:
        baseline_value = str(baseline.get(field, "")).strip()
        verification_value = str(verification.get(field, "")).strip()
        if not baseline_value:
            reasons.append(f"基线缺少{label}记录")
        elif baseline_value != verification_value:
            reasons.append(f"{label}已从「{baseline_value}」变为「{verification_value or '未知'}」")
    if not baseline.get("report_eligible", False):
        reasons.append("基线不是正式报告样本")
    if not verification.get("report_eligible", False):
        reasons.append("复测不是正式报告样本")
    if int(baseline.get("sample_size", 0)) != int(verification.get("sample_size", 0)):
        reasons.append(
            f"正式样本数已从 {int(baseline.get('sample_size', 0))} 变为 "
            f"{int(verification.get('sample_size', 0))}"
        )
    return reasons


async def verify_geo_cycle(
    project_id: str,
    cycle_id: str,
    session: Session,
) -> CycleVerificationResponse:
    cycle = session.get(GeoCycle, cycle_id)
    if cycle is None or cycle.project_id != project_id:
        raise ValueError("优化周期不存在")
    if cycle.status == "complete":
        return CycleVerificationResponse(
            cycle_id=cycle.id,
            status=cycle.status,
            verification_summary=cycle.verification_summary or {},
        )
    if cycle.stage != "verify":
        raise ValueError("必须先完成本周期的审批产物和实施记录，才能复测")
    config = cycle.measurement_config or {}
    if not config.get("questions") or not config.get("engine_ids"):
        raise ValueError("该周期没有可复用的基线测量配置")

    retest = _latest_cycle_retest(cycle.id, session)
    project = session.get(Project, project_id)
    cycle_brief_version = int(config.get("brief_version", 1))
    if project is None:
        raise ValueError("项目不存在")
    if cycle_brief_version != project.brief_version:
        if retest is not None:
            retest.status = "cancelled"
            retest.last_error = "研究 Brief 已更新；旧周期不能继续归因，请建立新基线"
            retest.updated_at = datetime.now(UTC)
            session.add(retest)
            session.commit()
        raise ValueError("研究 Brief 已更新；旧周期不能继续归因，请建立新基线")
    now = datetime.now(UTC)
    if retest is not None:
        retest.status = "running"
        retest.started_at = now
        retest.last_error = ""
        retest.updated_at = now
        session.add(retest)
    cycle.stage = "verify"
    cycle.status = "active"
    session.add(cycle)
    session.commit()

    try:
        response = await run_citations(
            CitationRunRequest(
                project_id=project_id,
                cycle_id=cycle.id,
                engine_ids=config["engine_ids"],
                prompts=config["questions"],
                brand_name=config.get("brand_name", ""),
                aliases=config.get("aliases", []),
                brand_domains=config.get("brand_domains", []),
                competitors=config.get("competitors", []),
                samples=config.get("samples", 3),
            ),
            session,
        )
        eligible_results = [result for result in response.results if result.report_eligible]
        expected_engines = set(config["engine_ids"])
        returned_engines = {result.engine_id for result in eligible_results}
        if returned_engines != expected_engines:
            missing = "、".join(sorted(expected_engines - returned_engines))
            details = "；".join(response.errors.values()) or (
                f"答案面 {missing or '未知'} 没有返回正式样本"
            )
            raise ValueError(f"复测没有获得可比较结果：{details}")
    except Exception as error:
        if retest is not None:
            failed_at = datetime.now(UTC)
            retest.status = "failed"
            retest.last_error = str(error)
            retest.updated_at = failed_at
            session.add(retest)
            session.commit()
        raise

    baseline_by_engine = {
        result["engine_id"]: result for result in cycle.baseline_summary.get("engines", [])
    }
    comparisons = []
    for result in eligible_results:
        current = result.model_dump()
        baseline = _normalized_baseline_scope(
            baseline_by_engine.get(result.engine_id, {}), session
        )
        scope_reasons = _comparison_scope_reasons(baseline, current)
        comparable = not scope_reasons
        comparisons.append(
            {
                "engine_id": result.engine_id,
                "baseline": baseline,
                "verification": current,
                "comparison_status": "comparable" if comparable else "scope_changed",
                "comparison_reasons": scope_reasons,
                "entity_delta": (
                    round(result.entity_sov - float(baseline.get("entity_sov", 0)), 3)
                    if comparable
                    else None
                ),
                "citation_delta": (
                    round(result.citation_sov - float(baseline.get("citation_sov", 0)), 3)
                    if comparable
                    else None
                ),
                "entity_assessment": (
                    _change_assessment(baseline, current, "entity")
                    if comparable
                    else "not_comparable"
                ),
                "citation_assessment": (
                    _change_assessment(baseline, current, "citation")
                    if comparable
                    else "not_comparable"
                ),
            }
        )

    deliveries = session.exec(
        select(DeliveryRecord)
        .where(
            DeliveryRecord.cycle_id == cycle.id,
            DeliveryRecord.status == "published",
        )
        .order_by(col(DeliveryRecord.published_at))
    ).all()
    changed_work_items = {
        item.id: item
        for item in session.exec(select(WorkItem).where(WorkItem.cycle_id == cycle.id)).all()
    }
    cycle_comparable = bool(comparisons) and all(
        item["comparison_status"] == "comparable" for item in comparisons
    )
    cycle.verification_summary = {
        "captured_at": datetime.now(UTC).isoformat(),
        "brief_version": cycle_brief_version,
        "comparison_status": "comparable" if cycle_comparable else "scope_changed",
        "comparison_note": (
            "复测与基线使用同一研究范围，可以评估变化。"
            if cycle_comparable
            else "复测范围与基线不一致，本次结果不能归因于已实施改动；请建立新基线。"
        ),
        "questions": config["questions"],
        "engines": comparisons,
        "changes": [
            {
                "work_item_id": delivery.work_item_id,
                "work_item_title": (
                    changed_work_items[delivery.work_item_id].title
                    if delivery.work_item_id in changed_work_items
                    else "已删除的优化工作"
                ),
                "artifact_id": delivery.artifact_id,
                "method": delivery.method,
                "target_url": delivery.target_url,
                "notes": delivery.notes,
                "published_at": (
                    delivery.published_at.isoformat() if delivery.published_at else None
                ),
            }
            for delivery in deliveries
        ],
    }
    cycle.stage = "complete"
    cycle.status = "complete"
    cycle.completed_at = datetime.now(UTC)
    if retest is not None:
        retest.status = "complete"
        retest.completed_at = cycle.completed_at
        retest.updated_at = cycle.completed_at
        session.add(retest)
    session.add(cycle)
    session.commit()
    return CycleVerificationResponse(
        cycle_id=cycle.id,
        status=cycle.status,
        verification_summary=cycle.verification_summary,
    )


async def run_due_cycle_retests(session: Session) -> DueRetestResponse:
    now = datetime.now(UTC)
    plans = session.exec(
        select(CycleRetestPlan)
        .where(
            CycleRetestPlan.status == "scheduled",
            CycleRetestPlan.scheduled_for <= now,
        )
        .order_by(col(CycleRetestPlan.scheduled_for))
    ).all()
    completed = 0
    failed = 0
    plan_ids: list[str] = []
    errors: dict[str, str] = {}
    for plan in plans:
        plan_ids.append(plan.id)
        try:
            await verify_geo_cycle(plan.project_id, plan.cycle_id, session)
            completed += 1
        except Exception as error:
            failed += 1
            errors[plan.id] = str(error)
    return DueRetestResponse(
        processed=len(plans),
        completed=completed,
        failed=failed,
        plan_ids=plan_ids,
        errors=errors,
    )
