"""rubric 打分：总分范围、breakdown 结构、engine override 生效。"""

from __future__ import annotations

from keeplix.engines import scoring

_RICH_SIGNALS = {
    "status": 200,
    "text_length": 1200,
    "title": "GEO 完全指南",
    "first_paragraph": "GEO 是让内容被 AI 引用的优化方法。" * 3,
    "avg_paragraph_length": 120,
    "headings": {"h1": 1, "h2": 3, "h3": 2, "h4": 0},
    "list_count": 2,
    "external_link_count": 4,
    "has_author": True,
    "has_date": True,
    "has_recent_year": True,
    "has_numbers": True,
    "has_percentages": True,
    "has_jsonld": True,
    "has_site_name": True,
    "preferred_source_hits": 1,
}

_POOR_SIGNALS = {"status": 404, "text_length": 10, "title": "", "headings": {}}


def test_total_within_range():
    result = scoring.score(_RICH_SIGNALS)
    assert 0 <= result["total"] <= 100
    assert result["total"] >= 70  # 富信号应拿高分


def test_poor_page_scores_low():
    assert scoring.score(_POOR_SIGNALS)["total"] < 30


def test_breakdown_has_all_dimensions():
    breakdown = scoring.score(_RICH_SIGNALS)["breakdown"]
    assert "walled_garden_presence" in breakdown
    assert "checks" in breakdown["walled_garden_presence"]


def test_engine_override_changes_weight():
    base = scoring.score(_RICH_SIGNALS)["breakdown"]
    ernie = scoring.score(_RICH_SIGNALS, engine_id="baidu_ernie")["breakdown"]
    # 文心把 walled_garden 权重从 10 提到 18（归一化后应更高）
    assert ernie["walled_garden_presence"]["weight"] > base["walled_garden_presence"]["weight"]


def test_llm_check_is_judged_not_dropped():
    # llm_* 项现由 llm_judge 评估：无 key 时走确定性 heuristic，evidence=llm_stub
    breakdown = scoring.score(_RICH_SIGNALS)["breakdown"]
    eeat_checks = {c["id"]: c for c in breakdown["authority_eeat"]["checks"]}
    tone = eeat_checks["llm_authority_tone"]
    assert tone["evidence"] in ("llm", "llm_stub")
    assert tone["got"] > 0  # 富信号（有作者+外链）应判出正分


def test_unknown_llm_check_is_safe():
    # 未知的 llm check id：安全记 0 + not_implemented（不崩）
    from keeplix.engines.llm_judge import judge

    got, evidence = judge("nonexistent_llm_check", {})
    assert got == 0.0
    assert evidence == "not_implemented"
