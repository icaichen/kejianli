from keeplix.engines.prompt_quality import classify_prompt, summarize_prompt_quality
from keeplix.models.enums import PromptIntent


def test_prompt_intents_cover_the_four_measurement_jobs():
    assert classify_prompt("可见力支持哪些模型", "可见力") == PromptIntent.branded
    assert classify_prompt("GEO 工具有哪些") == PromptIntent.category
    assert classify_prompt("如何提高 AI 引用率") == PromptIntent.problem
    assert classify_prompt("可见力 vs Semrush 哪个好") == PromptIntent.comparison


def test_prompt_quality_exposes_limited_scope():
    quality = summarize_prompt_quality(["GEO 工具有哪些", "如何提高 AI 引用率"])
    assert quality["status"] == "limited"
    assert quality["coverage"] == {
        "branded": 0,
        "category": 1,
        "problem": 1,
        "comparison": 0,
    }
    assert quality["warnings"]


def test_prompt_quality_marks_complete_intent_coverage():
    quality = summarize_prompt_quality(
        [
            "可见力是什么",
            "GEO 工具有哪些",
            "如何提高 AI 引用率",
            "GEO 工具对比",
        ],
        "可见力",
    )
    assert quality["status"] == "comprehensive"
    assert quality["missing_intents"] == []
