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


# --------------------------------------------------------------------------- #
# Prompt 集
# --------------------------------------------------------------------------- #
class Prompt(SQLModel, table=True):
    __tablename__ = "prompt"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    text: str
    intent: PromptIntent = PromptIntent.category
    active: bool = True


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
    project_id: str = Field(foreign_key="project.id", index=True)
    engine_id: str = Field(foreign_key="engine.id", index=True)
    samples: int = 3
    status: RunStatus = RunStatus.pending
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None


class CitationResult(SQLModel, table=True):
    __tablename__ = "citation_result"
    id: str = Field(default_factory=_uuid, primary_key=True)
    citation_run_id: str = Field(foreign_key="citation_run.id", index=True)
    prompt_id: str | None = Field(default=None, foreign_key="prompt.id")
    sample_index: int = 0
    answer_text: str = ""
    brand_mentioned: bool = False
    rank: int | None = None
    cited_urls: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    own_domain_cited: bool = False
    sentiment: Sentiment | None = None


class VisibilityScore(SQLModel, table=True):
    __tablename__ = "visibility_score"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    engine_id: str = Field(foreign_key="engine.id", index=True)
    period: datetime = Field(default_factory=_now)
    entity_sov: float = 0.0
    citation_sov: float = 0.0
    avg_rank: float | None = None
    sample_size: int = 0


class Deliverable(SQLModel, table=True):
    __tablename__ = "deliverable"
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    kind: DeliverableKind = DeliverableKind.audit_report
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)
