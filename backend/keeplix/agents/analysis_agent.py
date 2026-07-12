"""AnalysisAgent：URL → signals + score(breakdown)。"""

from __future__ import annotations

from dataclasses import dataclass

from keeplix.agents.base import Agent
from keeplix.engines import analysis, scoring
from keeplix.engines.llm_judge import prejudge_llm_checks


@dataclass
class AnalysisInput:
    url: str
    engine_id: str | None = None
    preferred_sources: list[str] | None = None


@dataclass
class AnalysisOutput:
    url: str
    status: int
    signals: dict
    total: int
    breakdown: dict


class AnalysisAgent(Agent[AnalysisInput, AnalysisOutput]):
    name = "analysis"

    async def run(self, payload: AnalysisInput) -> AnalysisOutput:
        fetched = await analysis.fetch(payload.url)
        signals = analysis.parse(fetched, preferred_sources=payload.preferred_sources)
        # 有 DeepSeek key 且有网 → 真实 LLM 判分；否则内部自动回退 heuristic。
        llm_judgments = await prejudge_llm_checks(signals)
        result = scoring.score(signals, engine_id=payload.engine_id, llm_judgments=llm_judgments)
        return AnalysisOutput(
            url=payload.url,
            status=fetched.status,
            signals=signals,
            total=result["total"],
            breakdown=result["breakdown"],
        )
