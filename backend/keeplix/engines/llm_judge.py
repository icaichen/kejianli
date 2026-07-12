"""LLM 判分层：rubric 里 method=llm 的 check 由此评估。

现实约束（见 docs/geo-rubric.md）：
- 有 LLM key 时 → `judge_async` 调用模型，evidence=`llm`。
- 无 key / 网络错 → 回退确定性 heuristic（从已有 signals 估算），evidence=`llm_stub`。
  这样骨架阶段 LLM 项也有意义的分数，且测试可重放；接了 key 自动升级。

调用点：
- 异步链路（analysis_service / agents）→ `prejudge_llm_checks` 并发预取，
  再把结果字典塞进 `scoring.score(..., llm_judgments=...)`。
- 同步链路 / 无网 / 测试 → `judge()` 仅走 heuristic。
"""

from __future__ import annotations

import asyncio
import re

import httpx

from keeplix.config import RUBRIC_ZH
from keeplix.core.config import get_settings
from keeplix.core.logging import get_logger

log = get_logger("engines.llm_judge")

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

# 每个 LLM check 的评估提示：告诉模型看什么、给什么样的分。
# 只塞相关信号，避免整段抓取污染上下文。
_LLM_PROMPTS = {
    "llm_authority_tone": (
        "你正在为一段网页内容做 GEO 权威度评分。请判断这段内容是否体现出可被 AI 引用的"
        "权威语气：作者可见、观点有据、数据/来源明确、避免空洞营销腔。\n"
        "只输出一个 0 到 1 之间的浮点数（保留两位小数），不要任何解释或标点。\n"
        "0.0=完全无权威信号；0.5=有一定专业性；1.0=作者/资质/数据/引用齐全。\n\n"
        "标题：{title}\n"
        "首段：{first_paragraph}\n"
        "是否署名作者：{has_author}\n"
        "外链数量：{external_link_count}\n"
        "正文摘要（前 800 字）：{text_snapshot}\n"
    ),
    "llm_faq_coverage": (
        "你正在评估一段网页内容对「用户常问问题」的覆盖度（GEO fan-out 场景）。\n"
        "只输出一个 0 到 1 之间的浮点数（保留两位小数），不要任何解释或标点。\n"
        "0.0=完全不涉及常见问题；0.5=隐含回答部分；1.0=明确 Q&A / FAQ 覆盖多角度。\n\n"
        "标题：{title}\n"
        "首段：{first_paragraph}\n"
        "列表结构数量：{list_count}\n"
        "正文长度：{text_length}\n"
        "正文摘要（前 1500 字）：{text_snapshot}\n"
    ),
}

_FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+")


def _heuristic(check_id: str, signals: dict) -> float:
    fn = _HEURISTICS.get(check_id)
    return round(fn(signals), 2) if fn else 0.0


def judge(check_id: str, signals: dict) -> tuple[float, str]:
    """同步判分：始终走 heuristic（供测试 / 不需要 LLM 的路径调用）。

    异步路径请使用 `judge_async` 或 `prejudge_llm_checks`——真实调用只发生在那里。
    """
    if check_id not in _HEURISTICS:
        return 0.0, "not_implemented"
    settings = get_settings()
    has_llm_key = bool(settings.deepseek_api_key or settings.openai_api_key)
    return _heuristic(check_id, signals), ("llm" if has_llm_key else "llm_stub")


async def judge_async(check_id: str, signals: dict) -> tuple[float, str]:
    """异步判分：有 key 且有网时调 LLM；任何失败降级 heuristic。"""
    if check_id not in _HEURISTICS:
        return 0.0, "not_implemented"

    settings = get_settings()
    if not settings.deepseek_api_key:
        return _heuristic(check_id, signals), "llm_stub"

    prompt_tpl = _LLM_PROMPTS.get(check_id)
    if not prompt_tpl:
        return _heuristic(check_id, signals), "llm_stub"

    text_snapshot = signals.get("text_snapshot", "") or ""
    prompt = prompt_tpl.format(
        title=signals.get("title", ""),
        first_paragraph=(signals.get("first_paragraph") or "")[:400],
        has_author=signals.get("has_author", False),
        external_link_count=signals.get("external_link_count", 0),
        list_count=signals.get("list_count", 0),
        text_length=signals.get("text_length", 0),
        text_snapshot=text_snapshot[:1500],
    )

    try:
        score = await _call_deepseek(
            prompt,
            settings.deepseek_api_key,
            settings.deepseek_base_url,
            settings.deepseek_model,
        )
        return round(max(0.0, min(1.0, score)), 2), "llm"
    except Exception as e:  # noqa: BLE001 - 网络/解析失败都降级
        log.info("LLM 判分失败（%s），降级 heuristic：%s", check_id, e)
        return _heuristic(check_id, signals), "llm_stub"


async def _call_deepseek(
    prompt: str, api_key: str, base_url: str, model: str = "deepseek-v4-flash"
) -> float:
    """调用 DeepSeek Chat Completions；提取回复文本中的第一个浮点数。"""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.0,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    m = _FLOAT_RE.search(text)
    if not m:
        raise ValueError(f"no float in response: {text!r}")
    return float(m.group(0))


def _list_llm_check_ids() -> list[str]:
    """从 rubric 里抓所有 method=llm 的 check id（供 prejudge 使用）。"""
    import yaml

    with open(RUBRIC_ZH, encoding="utf-8") as f:
        rubric = yaml.safe_load(f)
    ids: list[str] = []
    for dim in rubric.get("dimensions", {}).values():
        for c in dim.get("checks", []):
            if c.get("method") == "llm":
                ids.append(c["id"])
    return ids


async def prejudge_llm_checks(signals: dict) -> dict[str, tuple[float, str]]:
    """并发预取所有 LLM check 的判分，供 scoring.score(..., llm_judgments=...) 使用。"""
    ids = _list_llm_check_ids()
    if not ids:
        return {}
    results = await asyncio.gather(*(judge_async(cid, signals) for cid in ids))
    return dict(zip(ids, results, strict=True))
