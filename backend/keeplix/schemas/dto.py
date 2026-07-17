"""请求/响应 DTO。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# 分析
# --------------------------------------------------------------------------- #
class AnalysisRequest(BaseModel):
    url: str
    engine_id: str | None = Field(default=None, description="按引擎档评分；null=通用档")
    brand_name: str | None = None
    preferred_sources: list[str] | None = None
    project_id: str | None = None
    cycle_id: str | None = None


class RecommendationDTO(BaseModel):
    dimension: str
    title: str
    detail: str
    severity: str
    jsonld: dict | None = None
    compliance_flag: bool = False
    generated_content: str | None = None  # LLM 生成的现成内容（可直接用）


class AnalysisResponse(BaseModel):
    audit_run_id: str
    url: str
    status: int
    total: int = Field(description="GEO 总分 0–100")
    breakdown: dict
    recommendations: list[RecommendationDTO]


# --------------------------------------------------------------------------- #
# Citation 采样
# --------------------------------------------------------------------------- #
class CitationRunRequest(BaseModel):
    engine_ids: list[str]
    prompts: list[str]
    brand_name: str
    aliases: list[str] | None = None
    brand_domains: list[str] | None = None
    competitors: list[str] | None = None
    samples: int | None = Field(default=None, description="每 prompt 采样次数；null=用默认")
    project_id: str | None = None
    prompt_set_id: str | None = None
    cycle_id: str | None = None
    tracking_plan_id: str | None = None
    triggered_by: str = "user"


class SoVEngineResult(BaseModel):
    engine_id: str
    surface_name: str = ""
    acquisition: str = "stub"
    measurement_scope: str = "stub"
    report_eligible: bool = False
    measurement_quality: dict = Field(default_factory=dict)
    entity_sov: float
    citation_sov: float
    competitor_sov: dict[str, float] = Field(default_factory=dict)
    relative_sov: float | None = None
    avg_rank: float | None
    sample_size: int
    entity_ci_low: float
    entity_ci_high: float
    citation_ci_low: float
    citation_ci_high: float


class CitationRunResponse(BaseModel):
    results: list[SoVEngineResult]
    status: str = "done"
    errors: dict[str, str] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Provider 验证
# --------------------------------------------------------------------------- #
class ProviderValidationDTO(BaseModel):
    id: str
    engine_id: str
    profile_version: int
    status: str
    review_status: str
    provider_acquisition: str
    measurement_scope: str
    checks: dict[str, bool]
    evidence: list[dict]
    error_summary: str
    started_at: datetime
    finished_at: datetime | None
    reviewed_at: datetime | None
    review_notes: str


class ProviderValidationReview(BaseModel):
    decision: Literal["accepted", "rejected"]
    notes: str = Field(min_length=2, max_length=1000)


# --------------------------------------------------------------------------- #
# 项目
# --------------------------------------------------------------------------- #
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    primary_domain: str = ""
    client_name: str = "default"
    brand_name: str = ""
    competitors: list[str] = Field(default_factory=list)
    locale: str = "zh-CN"
    market: str = "中国"
    category: str = ""
    research_objective: str = ""


class ProjectUpdate(BaseModel):
    brand_name: str | None = Field(default=None, min_length=1, max_length=120)
    competitors: list[str] | None = None
    primary_domain: str | None = Field(default=None, max_length=255)
    market: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=160)
    research_objective: str | None = Field(default=None, max_length=2000)


class ProjectResponse(BaseModel):
    id: str
    name: str
    client_name: str
    brand_name: str
    competitors: list[str]
    primary_domain: str
    locale: str
    market: str
    category: str
    research_objective: str
    brief_version: int = 1
    brief_ready: bool = False
    brief_missing_fields: list[str] = Field(default_factory=list)
    status: str


class SiteProfileRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2000)


class SiteProfileEvidence(BaseModel):
    field: Literal["brand_name", "category", "summary", "language"]
    value: str
    source: str


class SiteProfileResponse(BaseModel):
    url: str
    status: int
    title: str
    brand_name: str
    category: str
    summary: str
    language: str
    evidence: list[SiteProfileEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BrandFactCreate(BaseModel):
    fact_type: Literal[
        "product", "audience", "proof", "pricing", "limitation", "policy"
    ] = "product"
    claim: str = Field(min_length=2, max_length=2000)
    source_url: str = Field(min_length=4, max_length=2000)


class BrandFactUpdate(BaseModel):
    fact_type: Literal[
        "product", "audience", "proof", "pricing", "limitation", "policy"
    ] | None = None
    claim: str | None = Field(default=None, min_length=2, max_length=2000)
    source_url: str | None = Field(default=None, min_length=4, max_length=2000)
    status: Literal["draft", "verified", "rejected"] | None = None


class BrandFactDTO(BaseModel):
    id: str
    project_id: str
    fact_type: str
    claim: str
    source_url: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class ResearchReportEngine(BaseModel):
    engine_id: str
    surface_name: str
    entity_sov: float
    citation_sov: float
    competitor_sov: dict[str, float] = Field(default_factory=dict)
    relative_sov: float | None = None
    sample_size: int


class ResearchReportCompetitor(BaseModel):
    name: str
    mention_count: int
    mention_rate: float


class ResearchReportSource(BaseModel):
    domain: str
    citation_count: int
    citation_share: float
    owned: bool = False


class ResearchReportFinding(BaseModel):
    kind: str
    title: str
    detail: str
    evidence: str


class ResearchReportIntent(BaseModel):
    intent: Literal["branded", "category", "problem", "comparison"]
    label: str
    sample_count: int
    entity_sov: float
    citation_sov: float
    competitor_sov: dict[str, float] = Field(default_factory=dict)


class ResearchReportDTO(BaseModel):
    project_id: str
    project_name: str
    client_name: str
    brand_name: str
    market: str
    category: str
    research_objective: str
    competitors: list[str]
    status: Literal["ready", "waiting_for_baseline"]
    generated_at: datetime
    brief_version: int
    tracking_plan_ids: list[str] = Field(default_factory=list)
    prompt_set_ids: list[str] = Field(default_factory=list)
    question_count: int = 0
    measurement_quality: dict = Field(default_factory=dict)
    period_start: datetime | None = None
    period_end: datetime | None = None
    qualified_run_count: int = 0
    sample_count: int = 0
    engine_count: int = 0
    entity_sov: float = 0.0
    citation_sov: float = 0.0
    discovery_sov: float = 0.0
    discovery_citation_sov: float = 0.0
    executive_summary: str
    intent_results: list[ResearchReportIntent] = Field(default_factory=list)
    engine_results: list[ResearchReportEngine] = Field(default_factory=list)
    competitor_results: list[ResearchReportCompetitor] = Field(default_factory=list)
    source_results: list[ResearchReportSource] = Field(default_factory=list)
    findings: list[ResearchReportFinding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    methodology: list[str] = Field(default_factory=list)


class ResearchQuestionItemDTO(BaseModel):
    id: str
    intent: Literal["branded", "category", "problem", "comparison"]
    text: str
    rationale: str
    selected: bool = True


class ResearchQuestionFrameworkDTO(BaseModel):
    project_id: str
    title: str
    summary: str
    recommended_samples: int = 2
    items: list[ResearchQuestionItemDTO]
    measurement_quality: dict = Field(default_factory=dict)


class PromptSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    prompts: list[str] = Field(min_length=1)
    kind: str = "tracking"


class PromptSetVersionCreate(BaseModel):
    prompts: list[str] = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=100)


class PromptSetResponse(BaseModel):
    id: str
    source_prompt_set_id: str | None
    name: str
    version: int
    kind: str
    active: bool
    brief_version: int = 1
    scope_current: bool = True
    prompts: list[str]
    prompt_items: list[dict] = Field(default_factory=list)
    measurement_quality: dict = Field(default_factory=dict)
    created_at: datetime


class TrackingPlanCreate(BaseModel):
    prompt_set_id: str
    engine_ids: list[str] = Field(min_length=1)
    samples: int = Field(default=3, ge=1, le=20)
    cadence: str = "weekly"
    next_run_at: datetime | None = None


class TrackingPlanResponse(BaseModel):
    id: str
    prompt_set_id: str
    prompt_set_name: str
    question_count: int
    prompt_items: list[dict] = Field(default_factory=list)
    measurement_quality: dict = Field(default_factory=dict)
    engine_ids: list[str]
    samples: int
    cadence: str
    status: str
    scope_current: bool = True
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    created_at: datetime


class VisibilitySnapshot(BaseModel):
    engine_id: str
    surface_name: str = ""
    acquisition: str = "api"
    measurement_scope: str = "citation"
    report_eligible: bool = True
    measurement_quality: dict = Field(default_factory=dict)
    entity_sov: float
    citation_sov: float
    competitor_sov: dict[str, float] = Field(default_factory=dict)
    relative_sov: float | None = None
    avg_rank: float | None
    sample_size: int
    entity_ci_low: float | None = None
    entity_ci_high: float | None = None
    citation_ci_low: float | None = None
    citation_ci_high: float | None = None
    period: datetime
    tracking_plan_id: str | None = None
    brief_version: int = 1
    scope_current: bool = True
    comparison_status: Literal["standalone", "baseline", "comparable", "scope_changed"]
    comparison_note: str
    previous_period: datetime | None = None
    entity_delta: float | None = None
    citation_delta: float | None = None


class TrackingExecutionResponse(BaseModel):
    plan_id: str
    status: str
    results: list[SoVEngineResult]
    errors: dict[str, str]
    last_run_at: datetime
    next_run_at: datetime | None


class DueTrackingResponse(BaseModel):
    checked_at: datetime
    executions: list[TrackingExecutionResponse]


class CitationEvidence(BaseModel):
    run_id: str
    activity_id: str | None
    engine_id: str
    captured_at: datetime
    prompt_text: str
    answer_text: str
    cited_urls: list[str]
    brand_mentioned: bool
    own_domain_cited: bool
    competitor_mentions: list[str] = Field(default_factory=list)
    request_id: str | None = None
    provider_metadata: dict = Field(default_factory=dict)
    surface_name: str = ""
    measurement_scope: str = "stub"
    report_eligible: bool = False
    brief_version: int = 1
    scope_current: bool = True


class VisibilityDiagnosis(BaseModel):
    """一个由正式答案面样本直接得出的诊断，不是自动生成的优化任务。"""

    id: str
    priority: str
    kind: str
    title: str
    detail: str
    engine_id: str
    prompt_text: str
    prompt_intent: str
    sample_size: int
    brand_mentions: int
    own_domain_citations: int
    competitor_mentions: dict[str, int] = Field(default_factory=dict)
    cited_urls: list[str] = Field(default_factory=list)
    evidence_run_ids: list[str] = Field(default_factory=list)


class DiagnosisSummary(BaseModel):
    qualified_sample_count: int = 0
    qualified_run_count: int = 0
    coverage_status: str = "unavailable"
    warnings: list[str] = Field(default_factory=list)
    insights: list[VisibilityDiagnosis] = Field(default_factory=list)


class ProjectActivityDTO(BaseModel):
    id: str
    kind: str
    title: str
    triggered_by: str
    status: str
    input_snapshot: dict
    output_summary: dict
    started_at: datetime
    finished_at: datetime | None


class CycleRetestPlanDTO(BaseModel):
    id: str
    cycle_id: str
    source_delivery_id: str
    status: str
    scheduled_for: datetime
    started_at: datetime | None
    completed_at: datetime | None
    last_error: str
    created_at: datetime
    updated_at: datetime


class GeoCycleDTO(BaseModel):
    id: str
    name: str
    objective: str
    stage: str
    status: str
    measurement_config: dict
    baseline_summary: dict
    verification_summary: dict
    retest_plan: CycleRetestPlanDTO | None = None
    started_at: datetime
    completed_at: datetime | None


class WorkItemDTO(BaseModel):
    id: str
    cycle_id: str
    source_activity_id: str | None
    title: str
    detail: str
    category: str
    priority: str
    status: str
    execution_mode: str
    evidence_snapshot: dict
    output_snapshot: dict
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class WorkItemUpdate(BaseModel):
    status: str | None = None
    execution_mode: str | None = None


class CycleVerificationResponse(BaseModel):
    cycle_id: str
    status: str
    verification_summary: dict


class DueRetestResponse(BaseModel):
    processed: int = 0
    completed: int = 0
    failed: int = 0
    plan_ids: list[str] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)


class OptimizationArtifactDTO(BaseModel):
    id: str
    work_item_id: str
    kind: str
    title: str
    version: int
    status: str
    content: str
    structured_content: dict
    source_snapshot: dict
    created_by: str
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    implemented_at: datetime | None


class ArtifactRevisionCreate(BaseModel):
    kind: str
    title: str
    content: str = ""
    structured_content: dict = Field(default_factory=dict)
    source_artifact_id: str | None = None


class ArtifactGenerateRequest(BaseModel):
    kind: Literal["content", "jsonld", "instructions"]
    engine_id: str = "deepseek"


class ArtifactStatusUpdate(BaseModel):
    status: str


class DeliveryRecordCreate(BaseModel):
    method: str = "manual"
    status: str = "published"
    target_url: str = ""
    notes: str = ""
    retest_after_days: int = Field(default=7, ge=1, le=30)


class DeliveryRecordDTO(BaseModel):
    id: str
    artifact_id: str
    work_item_id: str
    method: str
    status: str
    target_url: str
    notes: str
    created_by: str
    created_at: datetime
    published_at: datetime | None


class ArtifactExportResponse(BaseModel):
    filename: str
    media_type: str
    content: str
    delivery: DeliveryRecordDTO


class WorkItemDetail(BaseModel):
    item: WorkItemDTO
    artifacts: list[OptimizationArtifactDTO]
    deliveries: list[DeliveryRecordDTO]
    retest_plan: CycleRetestPlanDTO | None = None


class AgentPolicyUpdate(BaseModel):
    enabled: bool = True
    generation_engine: str = "deepseek"
    approval_required: bool = True
    max_actions_per_run: int = Field(default=3, ge=1, le=20)
    per_run_budget: float = Field(default=0.25, ge=0, le=100)
    monthly_budget: float = Field(default=5.0, ge=0, le=10000)
    auto_plan_on_tracking: bool = False


class AgentPolicyDTO(AgentPolicyUpdate):
    id: str
    project_id: str
    allow_direct_publish: bool
    created_at: datetime
    updated_at: datetime


class AgentRunCreate(BaseModel):
    cycle_id: str
    goal: str = "根据当前证据准备下一批优化草稿"


class AgentRunDecision(BaseModel):
    decision: str  # approve | reject | takeover


class AgentActionDTO(BaseModel):
    id: str
    work_item_id: str
    work_item_title: str
    source_artifact_id: str
    action_type: str
    status: str
    rationale: str
    estimated_cost: float
    output_artifact_id: str | None
    error_type: str | None


class AgentRunDTO(BaseModel):
    id: str
    cycle_id: str
    trigger: str
    goal: str
    status: str
    plan: dict
    estimated_cost: float
    actual_cost: float
    error_summary: dict
    attempt_count: int
    max_attempts: int
    heartbeat_at: datetime | None
    next_attempt_at: datetime | None
    created_at: datetime
    approved_at: datetime | None
    finished_at: datetime | None
    actions: list[AgentActionDTO]


class ProjectDashboard(ProjectResponse):
    """项目工作台：当前可见度基线与最近的历史采样。"""

    visibility: list[VisibilitySnapshot]
    citation_runs: int
    evidence: list[CitationEvidence]
    diagnosis: DiagnosisSummary
    prompt_sets: list[PromptSetResponse]
    tracking_plans: list[TrackingPlanResponse]
    activities: list[ProjectActivityDTO]
    cycles: list[GeoCycleDTO]
    work_items: list[WorkItemDTO]
    agent_policy: AgentPolicyDTO | None = None
    agent_runs: list[AgentRunDTO] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 服务交付（engagement）：Analysis + Recommendation + Citation → Deliverable
# --------------------------------------------------------------------------- #
class EngagementRequest(BaseModel):
    url: str = Field(description="要分析的目标页（通常是客户首页）")
    brand_name: str
    engine_ids: list[str] = Field(description="要跑可见度采样的引擎")
    prompts: list[str] = Field(description="采样用的代表性 prompt 集")
    aliases: list[str] | None = None
    brand_domains: list[str] | None = None
    competitors: list[str] | None = None
    preferred_sources: list[str] | None = None
    samples: int | None = None
    project_id: str | None = None


class EngagementReport(BaseModel):
    """一次交付的完整报告（也是 Deliverable.payload 的形状）。"""

    url: str
    brand_name: str
    total: int
    breakdown: dict
    recommendations: list[dict]
    visibility: list[dict]
    summary: str


class EngagementResponse(BaseModel):
    deliverable_id: str
    report: EngagementReport
    created_at: datetime
