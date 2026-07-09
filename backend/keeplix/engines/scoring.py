"""Rubric 打分引擎。只读 config/rubric.zh.yaml，不硬编码权重。见 docs/geo-rubric.md。

加一项 check：在 rubric.zh.yaml 加 {id,method,weight}，并在 CHECK_FUNCS 注册评估函数。
未注册/未实现的 check → 记 0 分 + evidence=not_implemented，不崩。
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Any

import yaml

from keeplix.config import RUBRIC_ZH
from keeplix.engines.llm_judge import judge

# check_id → 评估函数：输入 signals，返回 [0,1] 的达成比例
CheckFunc = Callable[[dict], float]


def _c(cond: bool) -> float:
    return 1.0 if cond else 0.0


CHECK_FUNCS: dict[str, CheckFunc] = {
    # technical_crawlability
    "http_ok": lambda s: _c(s.get("status") == 200),
    "ssr_content_visible": lambda s: _c(s.get("text_length", 0) >= 500),
    "has_title": lambda s: _c(bool(s.get("title"))),
    # content_structure
    "direct_answer_lead": lambda s: _c(20 <= len(s.get("first_paragraph", "")) <= 400),
    "heading_hierarchy": lambda s: _c(
        s.get("headings", {}).get("h1", 0) >= 1 and s.get("headings", {}).get("h2", 0) >= 1
    ),
    "qa_or_list_format": lambda s: _c(s.get("list_count", 0) >= 1),
    "paragraph_length": lambda s: _c(0 < s.get("avg_paragraph_length", 0) <= 300),
    # authority_eeat
    "has_author": lambda s: _c(s.get("has_author", False)),
    "has_outbound_citations": lambda s: _c(s.get("external_link_count", 0) >= 2),
    # freshness
    "has_date": lambda s: _c(s.get("has_date", False)),
    "recent_signal": lambda s: _c(s.get("has_recent_year", False)),
    # citation_friendliness
    "extractable_facts": lambda s: _c(s.get("has_numbers", False)),
    "data_expression": lambda s: _c(s.get("has_percentages", False)),
    # entity_alignment
    "has_jsonld": lambda s: _c(s.get("has_jsonld", False)),
    "entity_named": lambda s: _c(s.get("has_site_name", False)),
    # walled_garden_presence
    "links_to_preferred_sources": lambda s: _c(s.get("preferred_source_hits", 0) >= 1),
    # llm_* 留位：未实现
}


@lru_cache
def load_rubric() -> dict[str, Any]:
    with open(RUBRIC_ZH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _dimension_weights(rubric: dict, engine_id: str | None) -> dict[str, float]:
    """应用 engine_overrides 后重新归一化到 100。"""
    weights = {name: float(d["weight"]) for name, d in rubric["dimensions"].items()}
    if engine_id:
        for name, override in rubric.get("engine_overrides", {}).get(engine_id, {}).items():
            if name in weights and "weight" in override:
                weights[name] = float(override["weight"])
    total = sum(weights.values()) or 1.0
    return {name: w / total * 100 for name, w in weights.items()}


def score(signals: dict, engine_id: str | None = None) -> dict:
    """返回 {total, breakdown}。breakdown[dim] = {score, weight, checks:[{id,got,evidence}]}。"""
    rubric = load_rubric()
    dim_weights = _dimension_weights(rubric, engine_id)

    breakdown: dict[str, Any] = {}
    total = 0.0

    for dim_name, dim in rubric["dimensions"].items():
        dim_weight = dim_weights[dim_name]
        checks = dim.get("checks", [])
        check_weight_sum = sum(float(c["weight"]) for c in checks) or 1.0

        achieved = 0.0
        check_details = []
        for c in checks:
            cid = c["id"]
            method = c.get("method", "rule")
            if method == "llm":
                got, evidence = judge(cid, signals)
            else:
                fn = CHECK_FUNCS.get(cid)
                if fn is None:
                    got, evidence = 0.0, "not_implemented"
                else:
                    got = fn(signals)
                    evidence = (
                        "pass" if got >= 1.0 else ("partial" if got > 0 else "fail")
                    )
            achieved += got * float(c["weight"])
            check_details.append(
                {"id": cid, "method": method, "got": round(got, 2),
                 "evidence": evidence}
            )

        dim_score = achieved / check_weight_sum * dim_weight
        total += dim_score
        breakdown[dim_name] = {
            "score": round(dim_score, 1),
            "weight": round(dim_weight, 1),
            "checks": check_details,
        }

    return {"total": round(total), "breakdown": breakdown}
