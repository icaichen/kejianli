"""SQLModel 实体。与 docs/data-model.md 一一对应。

约定：
- 主键统一 UUID 字符串（跨库通用，SQLite/Postgres 都稳）。
- 列表/字典字段用 JSON 列。
- 时间用 UTC naive datetime（迁移期简单；后续可换 tz-aware）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from keeplix.models.enums import (
    Acquisition,
    DeliverableKind,
    ProjectStatus,
    PromptIntent,
    RunStatus,
    Sentiment,
    Severity,
)


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# 组织 / 客户 / 项目 / 品牌
# --------------------------------------------------------------------------- #
class Organization(SQLModel, table=True):
    __tablename__ = "organization"
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=_now)


class Client(SQLModel, table=True):
    __tablename__ = "client"
    id: str = Field(default_factory=_uuid, primary_key=True)
    org_id: str = Field(foreign_key="organization.id", index=True)
    name: str
    notes: str | None = None
    created_at: datetime = Field(default_factory=_now)


class Project(SQLModel, table=True):
    __tablename__ = "project"
    id: str = Field(default_factory=_uuid, primary_key=True)
    client_id: str = Field(foreign_key="client.id", index=True)
    name: str
    primary_domain: str = ""
    locale: str = "zh-CN"
    status: ProjectStatus = ProjectStatus.active
    created_at: datetime = Field(default_factory=_now)


class BrandEntity(SQLModel, table=True):
    __tablename__ = "brand_entity"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    brand_name: str
    aliases: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    domains: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    competitors: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class ProjectActivity(SQLModel, table=True):
    """项目中的一次完整动作：人工、计划任务或 Agent 均使用同一结构。"""

    __tablename__ = "project_activity"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    cycle_id: str | None = Field(default=None, foreign_key="geo_cycle.id", index=True)
    kind: str  # audit | visibility | optimization | agent
    title: str
    triggered_by: str = "user"  # user | schedule | agent
    status: RunStatus = RunStatus.pending
    input_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    output_summary: dict = Field(default_factory=dict, sa_column=Column(JSON))
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None


class GeoCycle(SQLModel, table=True):
    """One measurable GEO improvement loop: baseline -> work -> verification."""

    __tablename__ = "geo_cycle"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    name: str
    objective: str = "提升 AI 答案中的品牌可见度与引用"
    stage: str = "baseline"  # baseline | improve | execute | verify | complete
    status: str = "active"  # active | complete | cancelled
    measurement_config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    baseline_summary: dict = Field(default_factory=dict, sa_column=Column(JSON))
    verification_summary: dict = Field(default_factory=dict, sa_column=Column(JSON))
    started_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None


class WorkItem(SQLModel, table=True):
    """Actionable work shared by self-service, team delivery, and Agent execution."""

    __tablename__ = "work_item"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    cycle_id: str = Field(foreign_key="geo_cycle.id", index=True)
    source_activity_id: str | None = Field(
        default=None, foreign_key="project_activity.id", index=True
    )
    recommendation_id: str | None = Field(default=None, foreign_key="recommendation.id")
    title: str
    detail: str = ""
    category: str = "content"
    priority: Severity = Severity.medium
    status: str = "open"  # open | in_progress | review | done | dismissed
    execution_mode: str = "unassigned"  # unassigned | self | team | agent
    evidence_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    output_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None


class OptimizationArtifact(SQLModel, table=True):
    """Versioned output produced by a user, delivery team, or Agent for one work item."""

    __tablename__ = "optimization_artifact"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    cycle_id: str = Field(foreign_key="geo_cycle.id", index=True)
    work_item_id: str = Field(foreign_key="work_item.id", index=True)
    kind: str = "content"  # content | jsonld | instructions
    title: str
    version: int = 1
    status: str = "draft"  # draft | approved | implemented | superseded
    content: str = ""
    structured_content: dict = Field(default_factory=dict, sa_column=Column(JSON))
    source_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_by: str = "system"  # system | user | team | agent
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    approved_at: datetime | None = None
    implemented_at: datetime | None = None


class DeliveryRecord(SQLModel, table=True):
    """Auditable export or publication event for an approved optimization artifact."""

    __tablename__ = "delivery_record"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    cycle_id: str = Field(foreign_key="geo_cycle.id", index=True)
    work_item_id: str = Field(foreign_key="work_item.id", index=True)
    artifact_id: str = Field(foreign_key="optimization_artifact.id", index=True)
    method: str = "manual"  # export | manual | cms | repository
    status: str = "exported"  # exported | published
    target_url: str = ""
    notes: str = ""
    created_by: str = "user"  # user | team | agent
    created_at: datetime = Field(default_factory=_now)
    published_at: datetime | None = None


class AgentPolicy(SQLModel, table=True):
    """Project guardrails shared by every autonomous or assisted Agent run."""

    __tablename__ = "agent_policy"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", unique=True, index=True)
    enabled: bool = False
    generation_engine: str = "deepseek"
    approval_required: bool = True
    max_actions_per_run: int = 3
    per_run_budget: float = 0.25
    monthly_budget: float = 5.0
    allow_direct_publish: bool = False
    auto_plan_on_tracking: bool = False
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_run"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    cycle_id: str = Field(foreign_key="geo_cycle.id", index=True)
    activity_id: str | None = Field(default=None, foreign_key="project_activity.id", index=True)
    trigger: str = "user"  # user | tracking | schedule
    goal: str = ""
    status: str = "awaiting_approval"
    plan: dict = Field(default_factory=dict, sa_column=Column(JSON))
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    error_summary: dict = Field(default_factory=dict, sa_column=Column(JSON))
    attempt_count: int = 0
    max_attempts: int = 3
    heartbeat_at: datetime | None = None
    next_attempt_at: datetime | None = None
    created_at: datetime = Field(default_factory=_now)
    approved_at: datetime | None = None
    finished_at: datetime | None = None


class AgentAction(SQLModel, table=True):
    __tablename__ = "agent_action"
    id: str = Field(default_factory=_uuid, primary_key=True)
    agent_run_id: str = Field(foreign_key="agent_run.id", index=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    cycle_id: str = Field(foreign_key="geo_cycle.id", index=True)
    work_item_id: str = Field(foreign_key="work_item.id", index=True)
    source_artifact_id: str = Field(foreign_key="optimization_artifact.id")
    action_type: str = "draft_revision"
    status: str = "proposed"  # proposed | approved | running | done | failed | rejected
    rationale: str = ""
    estimated_cost: float = 0.0
    output_artifact_id: str | None = Field(default=None, foreign_key="optimization_artifact.id")
    error_type: str | None = None
    created_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None


# --------------------------------------------------------------------------- #
# 引擎目录（全局配置表，信源偏好在此，不硬编码）
# --------------------------------------------------------------------------- #
class Engine(SQLModel, table=True):
    __tablename__ = "engine"
    id: str = Field(primary_key=True)  # "deepseek" / "baidu_ernie" ...
    display_name: str
    acquisition: Acquisition = Acquisition.stub
    source_preferences: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    enabled: bool = True


class EngineQualification(SQLModel, table=True):
    """Human-reviewed eligibility for one concrete AI answer surface."""

    __tablename__ = "engine_qualification"
    engine_id: str = Field(foreign_key="engine.id", primary_key=True)
    surface_name: str
    expected_acquisition: str
    network_enabled: bool = False
    region_language: str = "zh-CN"
    auth_mode: str = "api_key"
    citation_availability: str = "none"  # none | urls | structured
    measurement_scope: str = "stub"  # stub | brand_awareness | answer_visibility | citation
    validation_status: str = "pending"  # pending | accepted | rejected
    report_eligible: bool = False
    last_validated_at: datetime | None = None
    validation_notes: str = ""
    cost_note: str = ""
    updated_at: datetime = Field(default_factory=_now)


class EngineRuntimeStatus(SQLModel, table=True):
    """Latest observed runtime health for one provider integration."""

    __tablename__ = "engine_runtime_status"
    engine_id: str = Field(foreign_key="engine.id", primary_key=True)
    status: str = "unknown"  # unknown | ready | degraded | not_connected
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str = ""
    last_observed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=_now)


# --------------------------------------------------------------------------- #
# Prompt 集
# --------------------------------------------------------------------------- #
class Prompt(SQLModel, table=True):
    __tablename__ = "prompt"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    prompt_set_id: str | None = Field(default=None, foreign_key="prompt_set.id", index=True)
    text: str
    intent: PromptIntent = PromptIntent.category
    active: bool = True


class PromptSet(SQLModel, table=True):
    __tablename__ = "prompt_set"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    source_prompt_set_id: str | None = Field(default=None, foreign_key="prompt_set.id", index=True)
    name: str
    version: int = 1
    kind: str = "tracking"  # tracking | exploration
    active: bool = True
    created_at: datetime = Field(default_factory=_now)


class TrackingPlan(SQLModel, table=True):
    """项目级持续追踪配置；实际运行仍落到 ProjectActivity + CitationRun。"""

    __tablename__ = "tracking_plan"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    prompt_set_id: str = Field(foreign_key="prompt_set.id", index=True)
    engine_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    samples: int = 3
    cadence: str = "weekly"  # manual | daily | weekly | monthly
    status: str = "active"  # active | paused
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# --------------------------------------------------------------------------- #
# 分析 / 评分 / 建议
# --------------------------------------------------------------------------- #
class Page(SQLModel, table=True):
    __tablename__ = "page"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str | None = Field(default=None, foreign_key="project.id", index=True)
    url: str
    last_fetched_at: datetime | None = None
    content_snapshot: str | None = None


class AuditRun(SQLModel, table=True):
    __tablename__ = "audit_run"
    id: str = Field(default_factory=_uuid, primary_key=True)
    activity_id: str | None = Field(default=None, foreign_key="project_activity.id", index=True)
    page_id: str = Field(foreign_key="page.id", index=True)
    engine_id: str | None = Field(default=None, foreign_key="engine.id")
    status: RunStatus = RunStatus.pending
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None


class Score(SQLModel, table=True):
    __tablename__ = "score"
    id: str = Field(default_factory=_uuid, primary_key=True)
    audit_run_id: str = Field(foreign_key="audit_run.id", index=True)
    total: int = 0
    breakdown: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Recommendation(SQLModel, table=True):
    __tablename__ = "recommendation"
    id: str = Field(default_factory=_uuid, primary_key=True)
    audit_run_id: str = Field(foreign_key="audit_run.id", index=True)
    dimension: str
    title: str
    detail: str = ""
    severity: Severity = Severity.medium
    jsonld: dict | None = Field(default=None, sa_column=Column(JSON))
    compliance_flag: bool = False


# --------------------------------------------------------------------------- #
# Citation 采样
# --------------------------------------------------------------------------- #
class CitationRun(SQLModel, table=True):
    __tablename__ = "citation_run"
    id: str = Field(default_factory=_uuid, primary_key=True)
    activity_id: str | None = Field(default=None, foreign_key="project_activity.id", index=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    prompt_set_id: str | None = Field(default=None, foreign_key="prompt_set.id", index=True)
    tracking_plan_id: str | None = Field(default=None, foreign_key="tracking_plan.id", index=True)
    engine_id: str = Field(foreign_key="engine.id", index=True)
    surface_name: str = ""
    provider_acquisition: str = "stub"
    measurement_scope: str = "stub"
    report_eligible: bool = False
    measurement_quality: dict = Field(default_factory=dict, sa_column=Column(JSON))
    samples: int = 3
    status: RunStatus = RunStatus.pending
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None


class CitationResult(SQLModel, table=True):
    __tablename__ = "citation_result"
    id: str = Field(default_factory=_uuid, primary_key=True)
    citation_run_id: str = Field(foreign_key="citation_run.id", index=True)
    prompt_id: str | None = Field(default=None, foreign_key="prompt.id")
    prompt_text: str = ""
    sample_index: int = 0
    answer_text: str = ""
    brand_mentioned: bool = False
    rank: int | None = None
    cited_urls: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    own_domain_cited: bool = False
    competitor_mentions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    sentiment: Sentiment | None = None
    raw_response: dict = Field(default_factory=dict, sa_column=Column(JSON))
    provider_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))


class VisibilityScore(SQLModel, table=True):
    __tablename__ = "visibility_score"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    engine_id: str = Field(foreign_key="engine.id", index=True)
    surface_name: str = ""
    tracking_plan_id: str | None = Field(default=None, foreign_key="tracking_plan.id", index=True)
    report_eligible: bool = False
    measurement_quality: dict = Field(default_factory=dict, sa_column=Column(JSON))
    period: datetime = Field(default_factory=_now)
    entity_sov: float = 0.0
    citation_sov: float = 0.0
    competitor_sov: dict = Field(default_factory=dict, sa_column=Column(JSON))
    relative_sov: float | None = None
    avg_rank: float | None = None
    sample_size: int = 0
    entity_ci_low: float | None = None
    entity_ci_high: float | None = None
    citation_ci_low: float | None = None
    citation_ci_high: float | None = None


class Deliverable(SQLModel, table=True):
    __tablename__ = "deliverable"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    cycle_id: str | None = Field(default=None, foreign_key="geo_cycle.id", index=True)
    kind: DeliverableKind = DeliverableKind.audit_report
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)
