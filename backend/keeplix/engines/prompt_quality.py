"""Deterministic prompt-intent classification and measurement coverage."""

from __future__ import annotations

from collections import Counter

from keeplix.models.enums import PromptIntent

_COMPARISON_MARKERS = ("对比", "比较", "区别", "哪个好", "最佳", "还是", "vs", "versus")
_PROBLEM_MARKERS = (
    "如何",
    "怎么",
    "为什么",
    "怎么办",
    "解决",
    "提高",
    "改善",
    "优化",
    "how",
    "why",
)
_ALL_INTENTS = tuple(intent.value for intent in PromptIntent)


def classify_prompt(
    text: str, brand_name: str = "", aliases: list[str] | None = None
) -> PromptIntent:
    normalized = text.casefold().strip()
    brand_terms = [brand_name, *(aliases or [])]
    if any(marker in normalized for marker in _COMPARISON_MARKERS):
        return PromptIntent.comparison
    if any(term.strip() and term.casefold() in normalized for term in brand_terms):
        return PromptIntent.branded
    if any(marker in normalized for marker in _PROBLEM_MARKERS):
        return PromptIntent.problem
    return PromptIntent.category


def summarize_prompt_quality(
    prompts: list[str], brand_name: str = "", aliases: list[str] | None = None
) -> dict[str, object]:
    intents = [classify_prompt(prompt, brand_name, aliases).value for prompt in prompts]
    counts = Counter(intents)
    coverage = {intent: counts.get(intent, 0) for intent in _ALL_INTENTS}
    covered = [intent for intent, count in coverage.items() if count > 0]
    missing = [intent for intent, count in coverage.items() if count == 0]
    status = (
        "comprehensive" if len(covered) == 4 else "balanced" if len(covered) >= 3 else "limited"
    )
    warnings = []
    if missing:
        warnings.append(f"缺少问题意图：{', '.join(missing)}")
    if len(prompts) < 8:
        warnings.append("问题数量较少，结果仅代表当前问题范围")
    return {
        "status": status,
        "question_count": len(prompts),
        "coverage": coverage,
        "covered_intents": covered,
        "missing_intents": missing,
        "warnings": warnings,
        "prompt_intents": [
            {"text": prompt, "intent": intent}
            for prompt, intent in zip(prompts, intents, strict=True)
        ],
    }
