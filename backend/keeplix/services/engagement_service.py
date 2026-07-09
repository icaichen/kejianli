"""服务交付编排：把 Analysis + Recommendation + Citation 串成一个 engagement，
产出一份 Deliverable（客户报告）。

这是「服务交付优先」业务线的核心：agency 给客户交付一次 GEO 服务，
内部就是跑这个 workflow。前端/客户端拿到 EngagementReport 即可成报告。
"""

from __future__ import annotations

from sqlmodel import Session

from keeplix.agents import (
    AnalysisAgent,
    AnalysisInput,
    RecommendationAgent,
    RecommendationInput,
    Workflow,
)
from keeplix.core.config import get_settings
from keeplix.models import Deliverable
from keeplix.models.enums import DeliverableKind
from keeplix.schemas import (
    CitationRunRequest,
    CitationRunResponse,
    EngagementReport,
    EngagementRequest,
    EngagementResponse,
)
from keeplix.services.citation_service import run_citations


def _executive_summary(total: int, recs: list, sov_results: list) -> str:
    high = sum(1 for r in recs if r.severity == "high")
    top_engine = max(sov_results, key=lambda r: r.entity_sov) if sov_results else None
    sov_line = (
        f"可见度最高的是 {top_engine.engine_id}（entity-SoV "
        f"{round(top_engine.entity_sov * 100)}%）。"
        if top_engine
        else "暂无可见度数据。"
    )
    return (
        f"GEO 总分 {total}/100；共 {len(recs)} 条优化建议（其中高优先级 {high} 条）。"
        f"{sov_line} 详见分项 breakdown 与建议清单。"
    )


async def run_engagement(req: EngagementRequest, session: Session) -> EngagementResponse:
    """跑一次完整交付流程：分析首页 → 建议 → 多引擎可见度 → 落库 Deliverable。"""
    wf = Workflow()
    samples = req.samples or get_settings().citation_samples

    # 1) 分析目标页（默认首页）
    analysis_out = await wf.step(
        "analysis",
        AnalysisAgent(),
        AnalysisInput(
            url=req.url,
            engine_id=None,  # 交付报告用通用档
            preferred_sources=req.preferred_sources,
        ),
    )

    # 2) 建议
    rec_out = await wf.step(
        "recommendation",
        RecommendationAgent(),
        RecommendationInput(
            url=req.url,
            breakdown=analysis_out.breakdown,
            brand_name=req.brand_name,
            first_paragraph=analysis_out.signals.get("first_paragraph"),
        ),
    )

    # 3) 多引擎可见度（复用 citation_service，可选落库）
    citation_resp: CitationRunResponse = await run_citations(
        CitationRunRequest(
            engine_ids=req.engine_ids,
            prompts=req.prompts,
            brand_name=req.brand_name,
            aliases=req.aliases,
            brand_domains=req.brand_domains,
            samples=samples,
            project_id=req.project_id,
        ),
        session,
    )

    # 4) 合成报告 + 落 Deliverable
    summary = _executive_summary(
        analysis_out.total, rec_out.items, citation_resp.results
    )
    report = EngagementReport(
        url=req.url,
        brand_name=req.brand_name,
        total=analysis_out.total,
        breakdown=analysis_out.breakdown,
        recommendations=[
            {
                "dimension": r.dimension,
                "title": r.title,
                "detail": r.detail,
                "severity": r.severity,
                "compliance_flag": r.compliance_flag,
                "generated_content": r.generated_content,
            }
            for r in rec_out.items
        ],
        visibility=[
            {
                "engine_id": v.engine_id,
                "entity_sov": v.entity_sov,
                "citation_sov": v.citation_sov,
                "avg_rank": v.avg_rank,
                "sample_size": v.sample_size,
            }
            for v in citation_resp.results
        ],
        summary=summary,
    )

    deliverable = Deliverable(
        project_id=req.project_id or "",
        kind=DeliverableKind.audit_report,
        payload=report.model_dump(),
    )
    session.add(deliverable)
    session.commit()
    session.refresh(deliverable)

    return EngagementResponse(
        deliverable_id=deliverable.id,
        report=report,
        created_at=deliverable.created_at,
    )
