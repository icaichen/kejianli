"""Guardrailed Agent planning and draft execution.

The Agent may claim evidence-backed work and create draft revisions. It never approves,
implements, or publishes artifacts; those transitions remain in the existing human flow.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from keeplix.models import (
    AgentAction,
    AgentPolicy,
    AgentRun,
    GeoCycle,
    OptimizationArtifact,
    Project,
    ProjectActivity,
    WorkItem,
)
from keeplix.models.enums import RunStatus
from keeplix.providers.registry import get_provider
from keeplix.schemas import (
    AgentActionDTO,
    AgentPolicyDTO,
    AgentPolicyUpdate,
    AgentRunCreate,
    AgentRunDTO,
)

_ACTION_COST = 0.02
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _policy_dto(policy: AgentPolicy) -> AgentPolicyDTO:
    return AgentPolicyDTO(
        id=policy.id,
        project_id=policy.project_id,
        enabled=policy.enabled,
        generation_engine=policy.generation_engine,
        approval_required=policy.approval_required,
        max_actions_per_run=policy.max_actions_per_run,
        per_run_budget=policy.per_run_budget,
        monthly_budget=policy.monthly_budget,
        allow_direct_publish=policy.allow_direct_publish,
        auto_plan_on_tracking=policy.auto_plan_on_tracking,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def get_agent_policy(project_id: str, session: Session) -> AgentPolicyDTO | None:
    policy = session.exec(select(AgentPolicy).where(AgentPolicy.project_id == project_id)).first()
    return _policy_dto(policy) if policy else None


def update_agent_policy(
    project_id: str, req: AgentPolicyUpdate, session: Session
) -> AgentPolicyDTO:
    if session.get(Project, project_id) is None:
        raise ValueError("项目不存在")
    policy = session.exec(select(AgentPolicy).where(AgentPolicy.project_id == project_id)).first()
    if policy is None:
        policy = AgentPolicy(project_id=project_id)
    policy.enabled = req.enabled
    policy.generation_engine = req.generation_engine
    policy.approval_required = True  # hard guardrail for this phase
    policy.max_actions_per_run = req.max_actions_per_run
    policy.per_run_budget = req.per_run_budget
    policy.monthly_budget = req.monthly_budget
    policy.allow_direct_publish = False
    policy.auto_plan_on_tracking = req.auto_plan_on_tracking
    policy.updated_at = datetime.now(UTC)
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return _policy_dto(policy)


def _run_dto(run: AgentRun, session: Session) -> AgentRunDTO:
    actions = session.exec(select(AgentAction).where(AgentAction.agent_run_id == run.id)).all()
    work_items = (
        {
            item.id: item
            for item in session.exec(
                select(WorkItem).where(WorkItem.id.in_([action.work_item_id for action in actions]))
            ).all()
        }
        if actions
        else {}
    )
    return AgentRunDTO(
        id=run.id,
        cycle_id=run.cycle_id,
        trigger=run.trigger,
        goal=run.goal,
        status=run.status,
        plan=run.plan,
        estimated_cost=run.estimated_cost,
        actual_cost=run.actual_cost,
        error_summary=run.error_summary,
        attempt_count=run.attempt_count,
        max_attempts=run.max_attempts,
        heartbeat_at=run.heartbeat_at,
        next_attempt_at=run.next_attempt_at,
        created_at=run.created_at,
        approved_at=run.approved_at,
        finished_at=run.finished_at,
        actions=[
            AgentActionDTO(
                id=action.id,
                work_item_id=action.work_item_id,
                work_item_title=(
                    work_items[action.work_item_id].title
                    if action.work_item_id in work_items
                    else "已删除的优化工作"
                ),
                source_artifact_id=action.source_artifact_id,
                action_type=action.action_type,
                status=action.status,
                rationale=action.rationale,
                estimated_cost=action.estimated_cost,
                output_artifact_id=action.output_artifact_id,
                error_type=action.error_type,
            )
            for action in actions
        ],
    )


def list_agent_runs(project_id: str, session: Session) -> list[AgentRunDTO]:
    runs = session.exec(
        select(AgentRun)
        .where(AgentRun.project_id == project_id)
        .order_by(col(AgentRun.created_at).desc())
        .limit(20)
    ).all()
    return [_run_dto(run, session) for run in runs]


def plan_agent_run(
    project_id: str, req: AgentRunCreate, session: Session, *, trigger: str = "user"
) -> AgentRunDTO:
    policy = session.exec(select(AgentPolicy).where(AgentPolicy.project_id == project_id)).first()
    if policy is None or not policy.enabled:
        raise ValueError("请先启用 Agent 策略")
    cycle = session.get(GeoCycle, req.cycle_id)
    if cycle is None or cycle.project_id != project_id or cycle.status != "active":
        raise ValueError("没有可执行的活跃优化周期")
    baseline_engines = cycle.baseline_summary.get("engines", [])
    if not any(engine.get("report_eligible") for engine in baseline_engines):
        raise ValueError("当前周期没有通过验收的真实答案面证据，Agent 不得执行")
    work_items = session.exec(
        select(WorkItem).where(
            WorkItem.cycle_id == cycle.id,
            WorkItem.status.not_in({"done", "dismissed"}),
        )
    ).all()
    work_items = sorted(
        work_items, key=lambda item: (_PRIORITY_ORDER.get(str(item.priority), 9), item.created_at)
    )
    candidates: list[tuple[WorkItem, OptimizationArtifact]] = []
    for item in work_items:
        artifact = session.exec(
            select(OptimizationArtifact)
            .where(
                OptimizationArtifact.work_item_id == item.id,
                OptimizationArtifact.kind.in_({"content", "instructions"}),
                OptimizationArtifact.status.not_in({"implemented", "superseded"}),
            )
            .order_by(col(OptimizationArtifact.version).desc())
        ).first()
        if artifact:
            candidates.append((item, artifact))
        if len(candidates) >= policy.max_actions_per_run:
            break
    if not candidates:
        raise ValueError("当前周期没有 Agent 可处理的内容草稿")
    estimated_cost = len(candidates) * _ACTION_COST
    if estimated_cost > policy.per_run_budget:
        raise ValueError("Agent 计划超出单次预算")
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = sum(
        run.actual_cost
        for run in session.exec(
            select(AgentRun).where(
                AgentRun.project_id == project_id,
                AgentRun.created_at >= month_start,
            )
        ).all()
    )
    if spent + estimated_cost > policy.monthly_budget:
        raise ValueError("Agent 计划超出本月预算")

    activity = ProjectActivity(
        project_id=project_id,
        cycle_id=cycle.id,
        kind="agent",
        title="Agent 提交优化计划",
        triggered_by=trigger,
        status=RunStatus.pending,
        input_snapshot={"goal": req.goal, "generation_engine": policy.generation_engine},
    )
    session.add(activity)
    session.flush()
    run = AgentRun(
        project_id=project_id,
        cycle_id=cycle.id,
        activity_id=activity.id,
        goal=req.goal,
        trigger=trigger,
        status="awaiting_approval",
        estimated_cost=estimated_cost,
        plan={
            "generation_engine": policy.generation_engine,
            "action_count": len(candidates),
            "approval_required": True,
            "allow_direct_publish": False,
        },
    )
    session.add(run)
    session.flush()
    for item, artifact in candidates:
        session.add(
            AgentAction(
                agent_run_id=run.id,
                project_id=project_id,
                cycle_id=cycle.id,
                work_item_id=item.id,
                source_artifact_id=artifact.id,
                rationale=f"优先处理{item.priority}优先级工作：{item.title}",
                estimated_cost=_ACTION_COST,
            )
        )
    session.commit()
    session.refresh(run)
    return _run_dto(run, session)


def decide_agent_run(project_id: str, run_id: str, decision: str, session: Session) -> AgentRunDTO:
    run = session.get(AgentRun, run_id)
    if run is None or run.project_id != project_id:
        raise ValueError("Agent 运行不存在")
    if decision not in {"approve", "reject", "takeover"}:
        raise ValueError("不支持的审批决定")
    if decision == "takeover":
        takeover_statuses = {
            "awaiting_approval",
            "approved",
            "running",
            "retry_scheduled",
            "partial",
            "failed",
        }
        if run.status not in takeover_statuses:
            raise ValueError("当前运行无法人工接管")
        run.status = "taken_over"
        run.finished_at = datetime.now(UTC)
        actions = session.exec(select(AgentAction).where(AgentAction.agent_run_id == run.id)).all()
        for action in actions:
            if action.status != "done":
                action.status = "rejected"
                session.add(action)
            item = session.get(WorkItem, action.work_item_id)
            if item and action.status != "done":
                item.execution_mode = "team"
                session.add(item)
        session.add(run)
        session.commit()
        session.refresh(run)
        return _run_dto(run, session)
    if run.status != "awaiting_approval":
        raise ValueError("Agent 计划已处理")
    actions = session.exec(select(AgentAction).where(AgentAction.agent_run_id == run.id)).all()
    if decision == "reject":
        run.status = "rejected"
        run.finished_at = datetime.now(UTC)
        for action in actions:
            action.status = "rejected"
            session.add(action)
    else:
        run.status = "approved"
        run.approved_at = datetime.now(UTC)
        for action in actions:
            action.status = "approved"
            session.add(action)
    session.add(run)
    session.commit()
    session.refresh(run)
    return _run_dto(run, session)


async def execute_agent_run(project_id: str, run_id: str, session: Session) -> AgentRunDTO:
    run = session.get(AgentRun, run_id)
    if run is None or run.project_id != project_id:
        raise ValueError("Agent 运行不存在")
    if run.status not in {"approved", "retry_scheduled"}:
        raise ValueError("Agent 计划必须先获得审批")
    policy = session.exec(select(AgentPolicy).where(AgentPolicy.project_id == project_id)).first()
    if policy is None or not policy.enabled:
        raise ValueError("Agent 策略已关闭")
    provider = get_provider(policy.generation_engine)
    if provider.acquisition == "stub":
        raise ValueError("Agent 不能使用 Stub Provider 生成客户产物")

    run.status = "running"
    run.attempt_count += 1
    run.heartbeat_at = datetime.now(UTC)
    run.next_attempt_at = None
    activity = session.get(ProjectActivity, run.activity_id) if run.activity_id else None
    if activity:
        activity.status = RunStatus.running
        session.add(activity)
    session.add(run)
    session.commit()
    actions = session.exec(select(AgentAction).where(AgentAction.agent_run_id == run.id)).all()
    errors: dict[str, str] = {}
    completed = 0
    for action in actions:
        if action.status == "done":
            completed += 1
            continue
        action.status = "running"
        run = session.get(AgentRun, run.id)
        run.heartbeat_at = datetime.now(UTC)
        session.add(run)
        session.add(action)
        session.commit()
        item = session.get(WorkItem, action.work_item_id)
        source = session.get(OptimizationArtifact, action.source_artifact_id)
        if item is None or source is None:
            action.status = "failed"
            action.error_type = "MissingSource"
            errors[action.id] = action.error_type
            session.add(action)
            session.commit()
            continue
        prompt = (
            "你是一名严谨的 GEO 内容编辑。基于下列已有信息修订草稿，"
            "提高结构清晰度、直接回答能力和实体表达。不得编造任何事实、数据、客户评价或引用。"
            "只输出可供人工审批的修订后内容。\n\n"
            f"工作目标：{item.title}\n诊断：{item.detail}\n已有草稿：\n{source.content}"
        )
        try:
            response = await provider.query(prompt)
            previous = session.exec(
                select(OptimizationArtifact).where(
                    OptimizationArtifact.work_item_id == item.id,
                    OptimizationArtifact.kind == source.kind,
                )
            ).all()
            for artifact in previous:
                if artifact.status != "implemented":
                    artifact.status = "superseded"
                    session.add(artifact)
            output = OptimizationArtifact(
                project_id=project_id,
                cycle_id=run.cycle_id,
                work_item_id=item.id,
                kind=source.kind,
                title=source.title,
                version=max(artifact.version for artifact in previous) + 1,
                status="draft",
                content=response.answer_text,
                structured_content=source.structured_content,
                source_snapshot={
                    **source.source_snapshot,
                    "agent_run_id": run.id,
                    "agent_action_id": action.id,
                    "generation_engine": policy.generation_engine,
                },
                created_by="agent",
            )
            session.add(output)
            session.flush()
            item.execution_mode = "agent"
            item.status = "review"
            item.updated_at = datetime.now(UTC)
            action.output_artifact_id = output.id
            action.status = "done"
            action.finished_at = datetime.now(UTC)
            completed += 1
            session.add(item)
            session.add(action)
            session.commit()
        except Exception as error:
            session.rollback()
            stored_action = session.get(AgentAction, action.id)
            if stored_action:
                stored_action.status = "failed"
                stored_action.error_type = type(error).__name__
                stored_action.finished_at = datetime.now(UTC)
                session.add(stored_action)
                session.commit()
            errors[action.id] = type(error).__name__

    run = session.get(AgentRun, run.id)
    retryable = bool(errors) and run.attempt_count < run.max_attempts
    if retryable:
        run.status = "retry_scheduled"
    elif not errors:
        run.status = "done"
    else:
        run.status = "partial" if completed else "failed"
    run.actual_cost = completed * _ACTION_COST
    run.error_summary = errors
    run.heartbeat_at = datetime.now(UTC)
    run.next_attempt_at = (
        datetime.now(UTC) + timedelta(minutes=2**run.attempt_count) if retryable else None
    )
    run.finished_at = None if retryable else datetime.now(UTC)
    session.add(run)
    if activity:
        activity = session.get(ProjectActivity, activity.id)
        if activity:
            activity.status = (
                RunStatus.pending if run.status == "retry_scheduled" else RunStatus(run.status)
            )
            activity.finished_at = run.finished_at
            activity.output_summary = {
                "agent_run_id": run.id,
                "completed_actions": completed,
                "failed_actions": len(errors),
                "actual_cost": run.actual_cost,
                "direct_publish": False,
            }
            session.add(activity)
    session.commit()
    session.refresh(run)
    return _run_dto(run, session)


def maybe_plan_from_tracking(
    project_id: str, cycle_id: str, session: Session
) -> AgentRunDTO | None:
    """Create a zero-cost proposal after tracking; never execute or spend automatically."""
    policy = session.exec(select(AgentPolicy).where(AgentPolicy.project_id == project_id)).first()
    if policy is None or not policy.enabled or not policy.auto_plan_on_tracking:
        return None
    existing = session.exec(
        select(AgentRun).where(
            AgentRun.project_id == project_id,
            AgentRun.cycle_id == cycle_id,
            AgentRun.status.in_({"awaiting_approval", "approved", "running", "retry_scheduled"}),
        )
    ).first()
    if existing:
        return None
    try:
        return plan_agent_run(
            project_id,
            AgentRunCreate(cycle_id=cycle_id, goal="追踪发现新的可见度信号，准备下一批优化草稿"),
            session,
            trigger="tracking",
        )
    except ValueError:
        return None


async def run_due_agent_runs(session: Session) -> list[AgentRunDTO]:
    now = datetime.now(UTC)
    stale_before = now - timedelta(minutes=10)
    stale = session.exec(
        select(AgentRun).where(AgentRun.status == "running", AgentRun.heartbeat_at < stale_before)
    ).all()
    for run in stale:
        run.status = "retry_scheduled"
        run.next_attempt_at = now
        session.add(run)
    session.commit()
    due = session.exec(
        select(AgentRun).where(
            AgentRun.status == "retry_scheduled",
            (AgentRun.next_attempt_at.is_(None)) | (AgentRun.next_attempt_at <= now),
        )
    ).all()
    results = []
    for run in due:
        results.append(await execute_agent_run(run.project_id, run.id, session))
    return results
