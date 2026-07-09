"""请求/响应 DTO。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# 分析
# --------------------------------------------------------------------------- #
class AnalysisRequest(BaseModel):
    url: str
    engine_id: str | None = Field(
        default=None, description="按引擎档评分；null=通用档"
    )
    brand_name: str | None = None
    preferred_sources: list[str] | None = None
    project_id: str | None = None


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
    samples: int | None = Field(default=None, description="每 prompt 采样次数；null=用默认")
    project_id: str | None = None


class SoVEngineResult(BaseModel):
    engine_id: str
    entity_sov: float
    citation_sov: float
    avg_rank: float | None
    sample_size: int


class CitationRunResponse(BaseModel):
    results: list[SoVEngineResult]


# --------------------------------------------------------------------------- #
# 项目
# --------------------------------------------------------------------------- #
class ProjectCreate(BaseModel):
    name: str
    primary_domain: str = ""
    client_name: str = "default"
    locale: str = "zh-CN"


class ProjectResponse(BaseModel):
    id: str
    name: str
    primary_domain: str
    locale: str
    status: str


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
