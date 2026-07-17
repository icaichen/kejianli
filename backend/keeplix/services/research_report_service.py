"""把最新正式答案证据聚合成面向企业客户的研究报告。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, cast
from urllib.parse import urlparse

from sqlmodel import Session, col, select

from keeplix.engines.prompt_quality import classify_prompt, summarize_prompt_quality
from keeplix.models import (
    BrandEntity,
    CitationResult,
    CitationRun,
    Client,
    Project,
    VisibilityScore,
)
from keeplix.schemas import (
    ResearchReportCompetitor,
    ResearchReportDTO,
    ResearchReportEngine,
    ResearchReportFinding,
    ResearchReportIntent,
    ResearchReportSource,
)

type IntentName = Literal["branded", "category", "problem", "comparison"]

_INTENT_LABELS: dict[IntentName, str] = {
    "branded": "品牌认知",
    "category": "品类发现",
    "problem": "需求发现",
    "comparison": "竞品比较",
}


def _percent(value: float) -> str:
    return f"{round(value * 100)}%"


def _domain(url: str) -> str | None:
    hostname = urlparse(url).hostname
    if not hostname:
        return None
    return hostname.lower().removeprefix("www.")


def _latest_by_engine[RowT](
    rows: list[RowT], engine_id: Callable[[RowT], str]
) -> list[RowT]:
    latest: dict[str, RowT] = {}
    for row in rows:
        latest.setdefault(engine_id(row), row)
    return list(latest.values())


def get_research_report(project_id: str, session: Session) -> ResearchReportDTO | None:
    project = session.get(Project, project_id)
    if project is None:
        return None
    client = session.get(Client, project.client_id)
    brand = session.exec(
        select(BrandEntity).where(BrandEntity.project_id == project_id)
    ).first()
    generated_at = datetime.now(UTC)
    brand_name = brand.brand_name if brand else project.name
    competitors = brand.competitors if brand else []
    aliases = brand.aliases if brand else []
    owned_domains = {
        domain
        for value in ([project.primary_domain] + (brand.domains if brand else []))
        if (domain := _domain(value if "://" in value else f"https://{value}"))
    }

    runs = list(
        session.exec(
            select(CitationRun)
            .where(
                CitationRun.project_id == project_id,
                CitationRun.brief_version == project.brief_version,
                CitationRun.report_eligible,
                CitationRun.status == "done",
            )
            .order_by(col(CitationRun.started_at).desc())
        ).all()
    )
    latest_runs = _latest_by_engine(runs, lambda row: row.engine_id)
    run_ids = [row.id for row in latest_runs]
    results = list(
        session.exec(
            select(CitationResult).where(col(CitationResult.citation_run_id).in_(run_ids))
        ).all()
    ) if run_ids else []

    scores = list(
        session.exec(
            select(VisibilityScore)
            .where(
                VisibilityScore.project_id == project_id,
                VisibilityScore.brief_version == project.brief_version,
                VisibilityScore.report_eligible,
            )
            .order_by(col(VisibilityScore.period).desc())
        ).all()
    )
    latest_scores = _latest_by_engine(scores, lambda row: row.engine_id)

    methodology = [
        "仅纳入已验收、可用于正式报告的真实答案面。",
        f"仅纳入当前研究 Brief v{project.brief_version} 的正式证据，旧范围只保留为历史记录。",
        "每个答案面采用最近一次成功运行，避免不同时点样本重复混算。",
        "非品牌发现率只统计不含品牌名的品类与需求问题；总体提及率包含品牌与比较问题。",
        "所有比率以当前正式样本数为分母；结果代表问题集范围，不代表全市场占有率。",
    ]
    if not results:
        return ResearchReportDTO(
            project_id=project.id,
            project_name=project.name,
            client_name=client.name if client else "",
            brand_name=brand_name,
            market=project.market,
            category=project.category,
            research_objective=project.research_objective,
            competitors=competitors,
            status="waiting_for_baseline",
            generated_at=generated_at,
            brief_version=project.brief_version,
            measurement_quality=summarize_prompt_quality([], brand_name, aliases),
            executive_summary="尚无可用于客户交付的正式答案证据。完成一次已验收答案面的基线测量后，系统会生成管理层摘要、竞品表现和来源结构。",
            warnings=["当前项目只有研究范围，尚未形成正式 AI 市场基线。"],
            methodology=methodology,
        )

    sample_count = len(results)
    brand_mentions = sum(result.brand_mentioned for result in results)
    owned_citations = sum(result.own_domain_cited for result in results)
    entity_sov = brand_mentions / sample_count
    citation_sov = owned_citations / sample_count
    prompt_texts = list(dict.fromkeys(result.prompt_text for result in results))
    measurement_quality = summarize_prompt_quality(prompt_texts, brand_name, aliases)
    grouped_results: dict[IntentName, list[CitationResult]] = {
        intent: [] for intent in _INTENT_LABELS
    }
    for result in results:
        intent = cast(IntentName, classify_prompt(result.prompt_text, brand_name, aliases).value)
        grouped_results[intent].append(result)
    intent_results = []
    for intent, label in _INTENT_LABELS.items():
        intent_samples = grouped_results[intent]
        intent_count = len(intent_samples)
        intent_results.append(
            ResearchReportIntent(
                intent=intent,
                label=label,
                sample_count=intent_count,
                entity_sov=(
                    sum(result.brand_mentioned for result in intent_samples) / intent_count
                    if intent_count else 0.0
                ),
                citation_sov=(
                    sum(result.own_domain_cited for result in intent_samples) / intent_count
                    if intent_count else 0.0
                ),
                competitor_sov={
                    name: sum(
                        name in result.competitor_mentions for result in intent_samples
                    ) / intent_count
                    for name in competitors
                } if intent_count else {},
            )
        )
    discovery_samples = grouped_results["category"] + grouped_results["problem"]
    discovery_count = len(discovery_samples)
    discovery_sov = (
        sum(result.brand_mentioned for result in discovery_samples) / discovery_count
        if discovery_count else 0.0
    )
    discovery_citation_sov = (
        sum(result.own_domain_cited for result in discovery_samples) / discovery_count
        if discovery_count else 0.0
    )
    competitor_counts = Counter(
        mention for result in results for mention in set(result.competitor_mentions)
    )
    competitor_results = [
        ResearchReportCompetitor(
            name=name,
            mention_count=competitor_counts[name],
            mention_rate=competitor_counts[name] / sample_count,
        )
        for name in competitors
    ]
    competitor_results.sort(key=lambda item: (-item.mention_count, item.name.lower()))

    source_counts = Counter(
        domain
        for result in results
        for url in set(result.cited_urls)
        if (domain := _domain(url))
    )
    total_citations = sum(source_counts.values())
    source_results = [
        ResearchReportSource(
            domain=domain,
            citation_count=count,
            citation_share=count / total_citations if total_citations else 0.0,
            owned=domain in owned_domains,
        )
        for domain, count in source_counts.most_common(10)
    ]
    engine_results = [
        ResearchReportEngine(
            engine_id=score.engine_id,
            surface_name=score.surface_name or score.engine_id,
            entity_sov=score.entity_sov,
            citation_sov=score.citation_sov,
            competitor_sov=score.competitor_sov,
            relative_sov=score.relative_sov,
            sample_size=score.sample_size,
        )
        for score in latest_scores
    ]
    engine_results.sort(key=lambda item: (-item.entity_sov, item.surface_name))

    findings: list[ResearchReportFinding] = []
    if discovery_count:
        findings.append(
            ResearchReportFinding(
                kind="discovery",
                title=(
                    f"{brand_name} 的非品牌自然发现率为 {_percent(discovery_sov)}"
                    if discovery_sov
                    else f"{brand_name} 尚未在非品牌问题中自然出现"
                ),
                detail=(
                    f"品类与需求问题不主动提供品牌名；该口径比包含品牌题的总体提及率"
                    f" {_percent(entity_sov)} 更能反映自然发现能力。"
                ),
                evidence=f"{discovery_count} 个品类与需求正式样本",
            )
        )
    if len(engine_results) > 1:
        strongest = engine_results[0]
        weakest = engine_results[-1]
        findings.append(
            ResearchReportFinding(
                kind="engine_gap",
                title=f"{strongest.surface_name} 是当前最强答案面",
                detail=f"{brand_name} 在该答案面的提及率为 {_percent(strongest.entity_sov)}。"
                + (
                    f"与最低的 {weakest.surface_name} 相差 "
                    f"{_percent(strongest.entity_sov - weakest.entity_sov)}。"
                    if strongest.engine_id != weakest.engine_id
                    else ""
                ),
                evidence=f"{strongest.sample_size} 个最新正式样本",
            )
        )
    top_competitor = next((item for item in competitor_results if item.mention_count > 0), None)
    if top_competitor:
        findings.append(
            ResearchReportFinding(
                kind="competitor",
                title=f"{top_competitor.name} 是当前最常出现的对照品牌",
                detail=(
                    f"该竞品在 {_percent(top_competitor.mention_rate)} 的样本中出现；"
                    f"{brand_name} 的提及率为 {_percent(entity_sov)}。"
                ),
                evidence=f"{top_competitor.mention_count}/{sample_count} 个正式样本",
            )
        )
    top_external = next((item for item in source_results if not item.owned), None)
    if top_external:
        findings.append(
            ResearchReportFinding(
                kind="source",
                title=f"{top_external.domain} 是主要外部引用来源",
                detail=(
                    f"该域名贡献 {_percent(top_external.citation_share)} 的已识别引用；"
                    f"自有域名在 {_percent(citation_sov)} 的答案样本中被引用。"
                ),
                evidence=f"{top_external.citation_count}/{total_citations} 次已识别来源引用",
            )
        )
    if not findings:
        findings.append(
            ResearchReportFinding(
                kind="baseline",
                title="正式基线已经建立",
                detail="当前样本尚未形成明显的答案面、竞品或来源差异，建议扩充问题覆盖后再判断。",
                evidence=f"{sample_count} 个正式样本",
            )
        )

    quality_warnings = list(dict.fromkeys(
        warning
        for run in latest_runs
        for warning in run.measurement_quality.get("warnings", [])
    ))
    warnings = quality_warnings.copy()
    if any(run.measurement_quality.get("status") == "limited" for run in latest_runs):
        warnings.insert(0, "当前问题意图覆盖有限，结论只能用于方向判断，不宜外推为完整市场结论。")

    top_competitor_text = (
        f"主要对照品牌 {top_competitor.name} 的样本出现率为 "
        f"{_percent(top_competitor.mention_rate)}。"
        if top_competitor
        else "当前样本未检测到已设定竞品提及。"
    )
    executive_summary = (
        f"本报告基于 {len(latest_runs)} 个正式答案面的 {sample_count} 个最新样本。"
        f"{brand_name} 在不含品牌名的品类与需求问题中自然发现率为 "
        f"{_percent(discovery_sov)}，总体提及率为 {_percent(entity_sov)}，"
        f"自有域名引用率为 {_percent(citation_sov)}。"
        f"{top_competitor_text} 结果用于回答“品牌在当前 AI 答案市场中的位置及其"
        "证据来源”，不等同于传统市场份额。"
    )
    period_values = [run.finished_at or run.started_at for run in latest_runs]
    return ResearchReportDTO(
        project_id=project.id,
        project_name=project.name,
        client_name=client.name if client else "",
        brand_name=brand_name,
        market=project.market,
        category=project.category,
        research_objective=project.research_objective,
        competitors=competitors,
        status="ready",
        generated_at=generated_at,
        brief_version=project.brief_version,
        tracking_plan_ids=list(dict.fromkeys(
            run.tracking_plan_id for run in latest_runs if run.tracking_plan_id
        )),
        prompt_set_ids=list(dict.fromkeys(
            run.prompt_set_id for run in latest_runs if run.prompt_set_id
        )),
        question_count=len(prompt_texts),
        measurement_quality=measurement_quality,
        period_start=min(period_values),
        period_end=max(period_values),
        qualified_run_count=len(latest_runs),
        sample_count=sample_count,
        engine_count=len(latest_runs),
        entity_sov=entity_sov,
        citation_sov=citation_sov,
        discovery_sov=discovery_sov,
        discovery_citation_sov=discovery_citation_sov,
        executive_summary=executive_summary,
        intent_results=intent_results,
        engine_results=engine_results,
        competitor_results=competitor_results,
        source_results=source_results,
        findings=findings,
        warnings=warnings,
        methodology=methodology,
    )
