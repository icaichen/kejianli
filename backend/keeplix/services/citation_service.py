"""Citation 编排：对每个引擎跑 CitationAgent → 落库 → SoV DTO。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session

from keeplix.agents import CitationAgent, CitationInput
from keeplix.core.config import get_settings
from keeplix.models import CitationResult, CitationRun, VisibilityScore
from keeplix.models.enums import RunStatus, Sentiment
from keeplix.schemas import CitationRunRequest, CitationRunResponse, SoVEngineResult


async def run_citations(req: CitationRunRequest, session: Session) -> CitationRunResponse:
    samples = req.samples or get_settings().citation_samples
    results: list[SoVEngineResult] = []

    for engine_id in req.engine_ids:
        run = CitationRun(
            project_id=req.project_id or "",
            engine_id=engine_id,
            samples=samples,
            status=RunStatus.running,
        )
        if req.project_id:
            session.add(run)
            session.flush()

        report = await CitationAgent().run(
            CitationInput(
                engine_id=engine_id,
                prompts=req.prompts,
                brand_name=req.brand_name,
                aliases=req.aliases,
                brand_domains=req.brand_domains,
                samples=samples,
            )
        )

        if req.project_id:
            for sp in report.samples:
                session.add(
                    CitationResult(
                        citation_run_id=run.id,
                        sample_index=sp.sample_index,
                        answer_text=sp.answer_text,
                        brand_mentioned=sp.brand_mentioned,
                        rank=sp.rank,
                        cited_urls=sp.cited_urls,
                        own_domain_cited=sp.own_domain_cited,
                        sentiment=Sentiment.neutral,
                    )
                )
            run.status = RunStatus.done
            run.finished_at = datetime.now(UTC)
            session.add(
                VisibilityScore(
                    project_id=req.project_id,
                    engine_id=engine_id,
                    entity_sov=report.entity_sov,
                    citation_sov=report.citation_sov,
                    avg_rank=report.avg_rank,
                    sample_size=report.sample_size,
                )
            )

        results.append(
            SoVEngineResult(
                engine_id=report.engine_id,
                entity_sov=report.entity_sov,
                citation_sov=report.citation_sov,
                avg_rank=report.avg_rank,
                sample_size=report.sample_size,
            )
        )

    if req.project_id:
        session.commit()

    return CitationRunResponse(results=results)
