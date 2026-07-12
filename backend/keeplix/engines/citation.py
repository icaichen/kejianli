"""Citation 采样聚合。见 docs/citation-engine.md。

对「引擎 × prompt」重复采样 N 次，解析每次回答，聚合成 entity-SoV / citation-SoV。
纯逻辑，provider 由外部注入（真实或 stub 都行），便于测试。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from urllib.parse import urlparse

from keeplix.providers.base import EngineProvider


@dataclass
class SampleParse:
    prompt: str
    sample_index: int
    answer_text: str
    brand_mentioned: bool
    cited_urls: list[str]
    own_domain_cited: bool
    rank: int | None = None
    raw_response: dict = field(default_factory=dict)


@dataclass
class SoVReport:
    engine_id: str
    entity_sov: float  # 品牌被点名率 [0,1]
    citation_sov: float  # 内容被引用率 [0,1]
    avg_rank: float | None
    sample_size: int
    entity_ci_low: float
    entity_ci_high: float
    citation_ci_low: float
    citation_ci_high: float
    samples: list[SampleParse] = field(default_factory=list)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Binomial proportion Wilson interval (95% by default).

    Citation sampling is categorical and often uses a small N. Wilson intervals avoid
    presenting a point estimate such as 0/3 as if the true rate were known exactly.
    """
    if total <= 0:
        return (0.0, 1.0)
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = (proportion + z**2 / (2 * total)) / denominator
    margin = (
        z * sqrt((proportion * (1 - proportion) / total) + (z**2 / (4 * total**2))) / denominator
    )
    return (round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3))


def _mention_rank(answer: str, brand_name: str, aliases: list[str]) -> int | None:
    """品牌首次出现的字符位置 → 粗略 rank（越靠前越小）。未提及返回 None。"""
    names = [brand_name, *aliases]
    positions = [answer.find(n) for n in names if n and answer.find(n) >= 0]
    if not positions:
        return None
    first = min(positions)
    # 粗分档：前 1/3=1，中段=2，后段=3
    third = max(len(answer) // 3, 1)
    return min(first // third + 1, 3)


def parse_response(
    prompt: str,
    sample_index: int,
    answer_text: str,
    cited_urls: list[str],
    brand_name: str,
    aliases: list[str],
    brand_domains: list[str],
) -> SampleParse:
    names = [brand_name, *aliases]
    mentioned = any(n and n in answer_text for n in names)
    own_cited = any(any(d in (urlparse(u).netloc or u) for d in brand_domains) for u in cited_urls)
    rank = _mention_rank(answer_text, brand_name, aliases) if mentioned else None
    return SampleParse(
        prompt=prompt,
        sample_index=sample_index,
        answer_text=answer_text,
        brand_mentioned=mentioned,
        cited_urls=cited_urls,
        own_domain_cited=own_cited,
        rank=rank,
    )


async def run_sampling(
    provider: EngineProvider,
    prompts: list[str],
    *,
    brand_name: str,
    aliases: list[str] | None = None,
    brand_domains: list[str] | None = None,
    samples: int = 3,
) -> SoVReport:
    """对每个 prompt 采样 samples 次，聚合成 SoVReport。"""
    aliases = aliases or []
    brand_domains = brand_domains or []
    parsed: list[SampleParse] = []

    for prompt in prompts:
        for i in range(samples):
            resp = await provider.query(prompt)
            # 优先用结构化 citations；若无则从文本提取 URL（fallback for DeepSeek 等）
            urls = [c.url for c in resp.cited_sources]
            if not urls:
                import re

                urls = re.findall(r"https?://[^\s\)）]+", resp.answer_text)
            parsed.append(
                parse_response(
                    prompt,
                    i,
                    resp.answer_text,
                    urls,
                    brand_name,
                    aliases,
                    brand_domains,
                )
            )
            parsed[-1].raw_response = resp.raw

    n = len(parsed) or 1
    entity_successes = sum(p.brand_mentioned for p in parsed)
    citation_successes = sum(p.own_domain_cited for p in parsed)
    entity_sov = entity_successes / n
    citation_sov = citation_successes / n
    entity_ci_low, entity_ci_high = wilson_interval(entity_successes, len(parsed))
    citation_ci_low, citation_ci_high = wilson_interval(citation_successes, len(parsed))
    ranks = [p.rank for p in parsed if p.rank is not None]
    avg_rank = (sum(ranks) / len(ranks)) if ranks else None

    return SoVReport(
        engine_id=getattr(provider, "engine_id", "unknown"),
        entity_sov=round(entity_sov, 3),
        citation_sov=round(citation_sov, 3),
        avg_rank=round(avg_rank, 2) if avg_rank is not None else None,
        sample_size=len(parsed),
        entity_ci_low=entity_ci_low,
        entity_ci_high=entity_ci_high,
        citation_ci_low=citation_ci_low,
        citation_ci_high=citation_ci_high,
        samples=parsed,
    )
