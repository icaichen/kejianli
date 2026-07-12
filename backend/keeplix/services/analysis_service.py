"""分析编排：AnalysisAgent + RecommendationAgent → 落库 → DTO。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session

from keeplix.agents import (
    AnalysisAgent,
    AnalysisInput,
    RecommendationAgent,
    RecommendationInput,
    Workflow,
)
from keeplix.models import AuditRun, Page, ProjectActivity, Recommendation, Score
from keeplix.models.enums import RunStatus, Severity
from keeplix.schemas import AnalysisRequest, AnalysisResponse, RecommendationDTO


async def run_analysis(req: AnalysisRequest, session: Session) -> AnalysisResponse:
    wf = Workflow()
    activity: ProjectActivity | None = None

    if req.project_id:
        activity = ProjectActivity(
            project_id=req.project_id,
            cycle_id=req.cycle_id,
            kind="audit",
            title="运行网站 GEO 审计",
            triggered_by="user",
            status=RunStatus.running,
            input_snapshot={
                "url": req.url,
                "engine_id": req.engine_id,
                "brand_name": req.brand_name,
            },
        )
        session.add(activity)
        session.commit()
        session.refresh(activity)

    try:
        analysis_out = await wf.step(
            "analysis",
            AnalysisAgent(),
            AnalysisInput(
                url=req.url,
                engine_id=req.engine_id,
                preferred_sources=req.preferred_sources,
            ),
        )
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
    except Exception as error:
        if activity:
            activity.status = RunStatus.failed
            activity.finished_at = datetime.now(UTC)
            activity.output_summary = {"error_type": type(error).__name__}
            session.add(activity)
            session.commit()
        raise

    # --- 落库 ---
    page = Page(
        project_id=req.project_id,
        url=req.url,
        last_fetched_at=datetime.now(UTC),
        content_snapshot=analysis_out.signals.get("text_snapshot"),
    )
    session.add(page)
    session.flush()

    audit = AuditRun(
        activity_id=activity.id if activity else None,
        page_id=page.id,
        engine_id=req.engine_id,
        status=RunStatus.done,
        finished_at=datetime.now(UTC),
    )
    session.add(audit)
    session.flush()

    session.add(
        Score(audit_run_id=audit.id, total=analysis_out.total, breakdown=analysis_out.breakdown)
    )

    rec_dtos: list[RecommendationDTO] = []
    for item in rec_out.items:
        session.add(
            Recommendation(
                audit_run_id=audit.id,
                dimension=item.dimension,
                title=item.title,
                detail=item.detail,
                severity=Severity(item.severity),
                jsonld=item.jsonld,
                compliance_flag=item.compliance_flag,
            )
        )
        rec_dtos.append(
            RecommendationDTO(
                dimension=item.dimension,
                title=item.title,
                detail=item.detail,
                severity=item.severity,
                jsonld=item.jsonld,
                compliance_flag=item.compliance_flag,
                generated_content=item.generated_content,
            )
        )

    session.commit()

    if activity:
        activity.status = RunStatus.done
        activity.finished_at = datetime.now(UTC)
        activity.output_summary = {
            "url": req.url,
            "total_score": analysis_out.total,
            "recommendation_count": len(rec_out.items),
            "high_priority_count": sum(1 for item in rec_out.items if item.severity == "high"),
        }
        session.add(activity)
        session.commit()

    return AnalysisResponse(
        audit_run_id=audit.id,
        url=req.url,
        status=analysis_out.status,
        total=analysis_out.total,
        breakdown=analysis_out.breakdown,
        recommendations=rec_dtos,
    )
