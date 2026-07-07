"""CitationAgent：prompts → 对某引擎采样 → SoV 报告。"""

from __future__ import annotations

from dataclasses import dataclass

from keeplix.agents.base import Agent
from keeplix.engines import citation
from keeplix.engines.citation import SoVReport
from keeplix.providers import get_provider


@dataclass
class CitationInput:
    engine_id: str
    prompts: list[str]
    brand_name: str
    aliases: list[str] | None = None
    brand_domains: list[str] | None = None
    samples: int = 3


class CitationAgent(Agent[CitationInput, SoVReport]):
    name = "citation"

    async def run(self, payload: CitationInput) -> SoVReport:
        provider = get_provider(
            payload.engine_id,
            brand_name=payload.brand_name,
            brand_domains=payload.brand_domains,
        )
        return await citation.run_sampling(
            provider,
            payload.prompts,
            brand_name=payload.brand_name,
            aliases=payload.aliases,
            brand_domains=payload.brand_domains,
            samples=payload.samples,
        )
