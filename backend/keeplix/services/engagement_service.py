"""Complete GEO cycle orchestration.

An engagement is not a disposable report. When attached to a project it creates a
measurable cycle, persists its audit and visibility baseline, and turns grounded
recommendations into a shared work queue for self-service, team, or Agent execution.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from keeplix.core.config import get_settings
from keeplix.models import (
    AuditRun,
    Deliverable,
    GeoCycle,
    OptimizationArtifact,
    Recommendation,
    WorkItem,
)
from keeplix.models.enums import DeliverableKind, Severity
from keeplix.schemas import (
    AnalysisRequest,
    CitationRunRequest,
    CitationRunResponse,
    EngagementReport,
    EngagementRequest,
    EngagementResponse,
)
from keeplix.services.analysis_service import run_analysis
from keeplix.services.citation_service import run_citations


def _executive_summary(total: int, recs: list, sov_results: list) -> str:
    high = sum(1 for recommendation in recs if recommendation.severity == "high")
    top_engine = max(sov_results, key=lambda result: result.entity_sov) if sov_results else None
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
    samples = req.samples or get_settings().citation_samples
    cycle: GeoCycle | None = None

    if req.project_id:
        cycle = GeoCycle(
            project_id=req.project_id,
            name=f"优化周期 {datetime.now(UTC).strftime('%Y-%m-%d')}",
        )
        session.add(cycle)
        session.commit()
        session.refresh(cycle)

    analysis = await run_analysis(
        AnalysisRequest(
            url=req.url,
            engine_id=None,
            brand_name=req.brand_name,
            preferred_sources=req.preferred_sources,
            project_id=req.project_id,
            cycle_id=cycle.id if cycle else None,
        ),
        session,
    )

    citation_response: CitationRunResponse = await run_citations(
        CitationRunRequest(
            engine_ids=req.engine_ids,
            prompts=req.prompts,
            brand_name=req.brand_name,
            aliases=req.aliases,
            brand_domains=req.brand_domains,
            samples=samples,
            project_id=req.project_id,
            cycle_id=cycle.id if cycle else None,
        ),
        session,
    )

    summary = _executive_summary(
        analysis.total, analysis.recommendations, citation_response.results
    )
    report = EngagementReport(
        url=req.url,
        brand_name=req.brand_name,
        total=analysis.total,
        breakdown=analysis.breakdown,
        recommendations=[item.model_dump() for item in analysis.recommendations],
        visibility=[result.model_dump() for result in citation_response.results],
        summary=summary,
    )

    deliverable = Deliverable(
        project_id=req.project_id or "",
        cycle_id=cycle.id if cycle else None,
        kind=DeliverableKind.audit_report,
        payload=report.model_dump(),
    )
    session.add(deliverable)

    if cycle and req.project_id:
        audit = session.get(AuditRun, analysis.audit_run_id)
        recommendations = session.exec(
            select(Recommendation).where(Recommendation.audit_run_id == analysis.audit_run_id)
        ).all()
        generated_by_title = {item.title: item for item in analysis.recommendations}
        for recommendation in recommendations:
            generated = generated_by_title.get(recommendation.title)
            work_item = WorkItem(
                project_id=req.project_id,
                cycle_id=cycle.id,
                source_activity_id=audit.activity_id if audit else None,
                recommendation_id=recommendation.id,
                title=recommendation.title,
                detail=recommendation.detail,
                category=recommendation.dimension,
                priority=Severity(recommendation.severity),
                evidence_snapshot={
                    "audit_run_id": analysis.audit_run_id,
                    "baseline_score": analysis.total,
                    "dimension": recommendation.dimension,
                },
                output_snapshot={
                    "generated_content": generated.generated_content if generated else None,
                    "jsonld": recommendation.jsonld,
                },
            )
            session.add(work_item)
            source_snapshot = {
                "audit_run_id": analysis.audit_run_id,
                "baseline_score": analysis.total,
                "recommendation_id": recommendation.id,
            }
            if generated and generated.generated_content:
                session.add(
                    OptimizationArtifact(
                        project_id=req.project_id,
                        cycle_id=cycle.id,
                        work_item_id=work_item.id,
                        kind="content",
                        title=f"{recommendation.title}·内容草稿",
                        content=generated.generated_content,
                        source_snapshot=source_snapshot,
                    )
                )
            if recommendation.jsonld:
                session.add(
                    OptimizationArtifact(
                        project_id=req.project_id,
                        cycle_id=cycle.id,
                        work_item_id=work_item.id,
                        kind="jsonld",
                        title=f"{recommendation.title}·JSON-LD",
                        structured_content=recommendation.jsonld,
                        source_snapshot=source_snapshot,
                    )
                )
            if not (generated and generated.generated_content) and not recommendation.jsonld:
                session.add(
                    OptimizationArtifact(
                        project_id=req.project_id,
                        cycle_id=cycle.id,
                        work_item_id=work_item.id,
                        kind="instructions",
                        title=f"{recommendation.title}·执行说明",
                        content=recommendation.detail,
                        source_snapshot=source_snapshot,
                    )
                )
        cycle.stage = "improve"
        cycle.measurement_config = {
            "questions": req.prompts,
            "engine_ids": req.engine_ids,
            "samples": samples,
            "brand_name": req.brand_name,
            "aliases": req.aliases or [],
            "brand_domains": req.brand_domains or [],
        }
        cycle.baseline_summary = {
            "captured_at": datetime.now(UTC).isoformat(),
            "engines": [result.model_dump() for result in citation_response.results],
        }
        session.add(cycle)

    session.commit()
    session.refresh(deliverable)
    return EngagementResponse(
        deliverable_id=deliverable.id,
        report=report,
        created_at=deliverable.created_at,
    )
