"""Citation orchestration with per-engine failure isolation."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from keeplix.agents import CitationAgent, CitationInput
from keeplix.core.config import get_settings
from keeplix.engines.prompt_quality import summarize_prompt_quality
from keeplix.models import (
    BrandEntity,
    CitationResult,
    CitationRun,
    ProjectActivity,
    VisibilityScore,
)
from keeplix.models.enums import RunStatus, Sentiment
from keeplix.providers import get_provider
from keeplix.schemas import CitationRunRequest, CitationRunResponse, SoVEngineResult
from keeplix.services.qualification_service import get_qualification, is_formally_eligible


def _provider_error(error: Exception) -> str:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    message = ""
    try:
        payload = response.json() if response is not None else {}
        error_payload = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error_payload.get("message", "") if isinstance(error_payload, dict) else ""
    except Exception:
        message = ""
    retry_after = (
        getattr(response, "headers", {}).get("retry-after") if response is not None else None
    )
    if status_code == 429:
        detail = message[:400] or "请求过于频繁或当前额度不可用"
        return f"HTTP 429：{detail}" + (f"；{retry_after} 秒后可重试" if retry_after else "")
    if status_code:
        return f"HTTP {status_code}：{type(error).__name__}"
    return type(error).__name__


async def run_citations(req: CitationRunRequest, session: Session) -> CitationRunResponse:
    samples = req.samples or get_settings().citation_samples
    results: list[SoVEngineResult] = []
    errors: dict[str, str] = {}
    activity: ProjectActivity | None = None
    measurement_quality = summarize_prompt_quality(req.prompts, req.brand_name, req.aliases)
    competitors = list(
        dict.fromkeys(item.strip() for item in (req.competitors or []) if item.strip())
    )

    if req.project_id:
        brand = session.exec(
            select(BrandEntity).where(BrandEntity.project_id == req.project_id)
        ).first()
        if brand is None:
            brand = BrandEntity(
                project_id=req.project_id,
                brand_name=req.brand_name,
                aliases=req.aliases or [],
                domains=req.brand_domains or [],
                competitors=competitors,
            )
            session.add(brand)
        elif req.competitors is not None:
            brand.competitors = competitors
            session.add(brand)
        activity = ProjectActivity(
            project_id=req.project_id,
            cycle_id=req.cycle_id,
            kind="visibility",
            title="运行 AI 可见度检测" if req.triggered_by == "user" else "执行追踪计划",
            triggered_by=req.triggered_by,
            status=RunStatus.running,
            input_snapshot={
                "questions": req.prompts,
                "engine_ids": req.engine_ids,
                "samples_per_question": samples,
                "brand_name": req.brand_name,
                "brand_domains": req.brand_domains or [],
                "tracking_plan_id": req.tracking_plan_id,
                "measurement_quality": measurement_quality,
                "competitors": competitors,
            },
        )
        session.add(activity)
        session.commit()
        session.refresh(activity)

    for engine_id in req.engine_ids:
        provider = get_provider(
            engine_id,
            brand_name=req.brand_name,
            brand_domains=req.brand_domains,
        )
        acquisition = str(getattr(provider, "acquisition", "stub"))
        measurement_scope = str(getattr(provider, "measurement_scope", "stub"))
        qualification = get_qualification(engine_id, session)
        report_eligible = is_formally_eligible(qualification, acquisition, measurement_scope)
        run: CitationRun | None = None
        if req.project_id:
            run = CitationRun(
                project_id=req.project_id,
                activity_id=activity.id if activity else None,
                prompt_set_id=req.prompt_set_id,
                tracking_plan_id=req.tracking_plan_id,
                engine_id=engine_id,
                surface_name=qualification.surface_name,
                provider_acquisition=acquisition,
                measurement_scope=measurement_scope,
                report_eligible=report_eligible,
                measurement_quality=measurement_quality,
                samples=samples,
                status=RunStatus.running,
            )
            session.add(run)
            session.commit()
            session.refresh(run)

        try:
            report = await CitationAgent().run(
                CitationInput(
                    engine_id=engine_id,
                    prompts=req.prompts,
                    brand_name=req.brand_name,
                    aliases=req.aliases,
                    brand_domains=req.brand_domains,
                    competitors=competitors,
                    samples=samples,
                )
            )
        except Exception as error:  # one provider must not erase other engines' evidence
            errors[engine_id] = _provider_error(error)
            if run:
                run.status = RunStatus.failed
                run.finished_at = datetime.now(UTC)
                session.add(run)
                session.commit()
            continue

        if req.project_id and run:
            for sample in report.samples:
                session.add(
                    CitationResult(
                        citation_run_id=run.id,
                        sample_index=sample.sample_index,
                        prompt_text=sample.prompt,
                        answer_text=sample.answer_text,
                        brand_mentioned=sample.brand_mentioned,
                        rank=sample.rank,
                        cited_urls=sample.cited_urls,
                        own_domain_cited=sample.own_domain_cited,
                        competitor_mentions=sample.competitor_mentions,
                        sentiment=Sentiment.neutral,
                        raw_response=sample.raw_response,
                        provider_metadata={
                            key: sample.raw_response.get(key)
                            for key in (
                                "provider",
                                "request_id",
                                "agent_id",
                                "agent_version",
                                "model",
                                "citation_enabled",
                            )
                            if key in sample.raw_response
                        },
                    )
                )
            run.status = RunStatus.done
            run.finished_at = datetime.now(UTC)
            session.add(run)
            if report_eligible:
                session.add(
                    VisibilityScore(
                        project_id=req.project_id,
                        engine_id=engine_id,
                        surface_name=qualification.surface_name,
                        tracking_plan_id=req.tracking_plan_id,
                        report_eligible=True,
                        measurement_quality=measurement_quality,
                        competitor_sov=report.competitor_sov,
                        relative_sov=report.relative_sov,
                        entity_sov=report.entity_sov,
                        citation_sov=report.citation_sov,
                        avg_rank=report.avg_rank,
                        sample_size=report.sample_size,
                        entity_ci_low=report.entity_ci_low,
                        entity_ci_high=report.entity_ci_high,
                        citation_ci_low=report.citation_ci_low,
                        citation_ci_high=report.citation_ci_high,
                    )
                )
            session.commit()

        results.append(
            SoVEngineResult(
                engine_id=report.engine_id,
                surface_name=qualification.surface_name,
                acquisition=acquisition,
                measurement_scope=measurement_scope,
                report_eligible=report_eligible,
                measurement_quality=measurement_quality,
                competitor_sov=report.competitor_sov,
                relative_sov=report.relative_sov,
                entity_sov=report.entity_sov,
                citation_sov=report.citation_sov,
                avg_rank=report.avg_rank,
                sample_size=report.sample_size,
                entity_ci_low=report.entity_ci_low,
                entity_ci_high=report.entity_ci_high,
                citation_ci_low=report.citation_ci_low,
                citation_ci_high=report.citation_ci_high,
            )
        )

    status = "done" if not errors else "partial" if results else "failed"
    if activity:
        stored_activity = session.get(ProjectActivity, activity.id)
        if stored_activity:
            stored_activity.status = RunStatus(status)
            stored_activity.finished_at = datetime.now(UTC)
            stored_activity.output_summary = {
                "engines": [result.model_dump() for result in results],
                "question_count": len(req.prompts),
                "sample_count": sum(result.sample_size for result in results),
                "errors": errors,
                "status": status,
                "measurement_quality": measurement_quality,
            }
            session.add(stored_activity)
            session.commit()

    return CitationRunResponse(results=results, status=status, errors=errors)
