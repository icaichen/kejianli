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
from keeplix.models import AuditRun, Page, Recommendation, Score
from keeplix.models.enums import RunStatus, Severity
from keeplix.schemas import AnalysisRequest, AnalysisResponse, RecommendationDTO


async def run_analysis(req: AnalysisRequest, session: Session) -> AnalysisResponse:
    wf = Workflow()

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
            url=req.url, breakdown=analysis_out.breakdown, brand_name=req.brand_name
        ),
    )

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
        page_id=page.id,
        engine_id=req.engine_id,
        status=RunStatus.done,
        finished_at=datetime.now(UTC),
    )
    session.add(audit)
    session.flush()

    session.add(Score(audit_run_id=audit.id, total=analysis_out.total,
                      breakdown=analysis_out.breakdown))

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
                dimension=item.dimension, title=item.title, detail=item.detail,
                severity=item.severity, jsonld=item.jsonld,
                compliance_flag=item.compliance_flag,
            )
        )

    session.commit()

    return AnalysisResponse(
        audit_run_id=audit.id,
        url=req.url,
        status=analysis_out.status,
        total=analysis_out.total,
        breakdown=analysis_out.breakdown,
        recommendations=rec_dtos,
    )
