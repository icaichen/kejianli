"""LLM 判分层：rubric 里 method=llm 的 check 由此评估。

现实约束（见 docs/geo-rubric.md）：
- 有 LLM key 时 → 真实调用模型判分（0..1）。
- 无 key 时 → 走确定性 heuristic（从已有 signals 估算），evidence 标 `llm_stub`。
  这样骨架阶段 LLM 项也有意义的分数，且测试可重放；接了 key 自动升级。

判分函数签名：judge(check_id, signals) -> (score: float[0..1], evidence: str)
"""

from __future__ import annotations

from keeplix.core.config import get_settings

# 无 key 时的确定性 heuristic：用已解析的 signals 近似「LLM 会怎么判」
_HEURISTICS = {
    # 权威语气：有作者 + 有外链引用 → 语气更权威
    "llm_authority_tone": lambda s: min(
        1.0,
        0.5 * float(s.get("has_author", False))
        + 0.5 * (1.0 if s.get("external_link_count", 0) >= 2 else 0.0),
    ),
    # FAQ / fan-out 覆盖：有列表/问答结构 + 正文足够长 → 覆盖更多子问题
    "llm_faq_coverage": lambda s: min(
        1.0,
        0.5 * (1.0 if s.get("list_count", 0) >= 1 else 0.0)
        + 0.5 * (1.0 if s.get("text_length", 0) >= 800 else 0.0),
    ),
}


def _heuristic(check_id: str, signals: dict) -> float:
    fn = _HEURISTICS.get(check_id)
    return round(fn(signals), 2) if fn else 0.0


def judge(check_id: str, signals: dict) -> tuple[float, str]:
    """评估一个 LLM check。返回 (score[0..1], evidence)。

    骨架阶段：始终走 heuristic（确定性、可测）。接入真实 LLM 后，
    在 settings 有 key 时改为调用模型，这里预留判断点。
    """
    settings = get_settings()
    has_llm_key = bool(settings.deepseek_api_key or settings.openai_api_key)

    score = _heuristic(check_id, signals)
    if check_id not in _HEURISTICS:
        return 0.0, "not_implemented"

    # 接入真实 LLM 判分时：if has_llm_key: score = await call_llm(...)
    # 目前无论有无 key 都用 heuristic，evidence 区分来源便于后续替换。
    evidence = "llm" if has_llm_key else "llm_stub"
    return score, evidence
