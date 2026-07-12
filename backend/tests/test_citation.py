"""citation 采样：stub 确定性 + 聚合正确。"""

from __future__ import annotations

import pytest

from keeplix.engines import citation
from keeplix.engines.citation import parse_response, wilson_interval
from keeplix.providers.stub import StubProvider


def test_stub_is_deterministic():
    p1 = StubProvider("deepseek", brand_name="keeplix")
    p2 = StubProvider("deepseek", brand_name="keeplix")
    import asyncio

    r1 = asyncio.run(p1.query("最好的 GEO 工具"))
    r2 = asyncio.run(p2.query("最好的 GEO 工具"))
    assert r1.answer_text == r2.answer_text
    assert [c.url for c in r1.cited_sources] == [c.url for c in r2.cited_sources]


def test_parse_response_detects_brand_and_own_domain():
    sp = parse_response(
        prompt="q",
        sample_index=0,
        answer_text="推荐使用 keeplix，效果不错。",
        cited_urls=["https://keeplix.com/post", "https://baike.baidu.com/x"],
        brand_name="keeplix",
        aliases=[],
        brand_domains=["keeplix.com"],
    )
    assert sp.brand_mentioned is True
    assert sp.own_domain_cited is True
    assert sp.rank == 1


@pytest.mark.asyncio
async def test_run_sampling_aggregates_sov():
    provider = StubProvider("deepseek", brand_name="keeplix", brand_domains=["keeplix.com"])
    report = await citation.run_sampling(
        provider,
        ["最好的 GEO 工具", "中文内容优化"],
        brand_name="keeplix",
        brand_domains=["keeplix.com"],
        samples=3,
    )
    assert report.sample_size == 6
    assert 0.0 <= report.entity_sov <= 1.0
    assert 0.0 <= report.citation_sov <= 1.0
    assert report.engine_id == "deepseek"
    assert 0.0 <= report.entity_ci_low <= report.entity_sov <= report.entity_ci_high <= 1.0
    assert 0.0 <= report.citation_ci_low <= report.citation_sov <= report.citation_ci_high <= 1.0


def test_wilson_interval_exposes_small_sample_uncertainty():
    assert wilson_interval(0, 3) == (0.0, 0.562)
    assert wilson_interval(3, 3) == (0.438, 1.0)
