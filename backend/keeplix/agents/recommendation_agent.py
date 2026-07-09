"""RecommendationAgent：score breakdown → 可执行建议清单 + Schema JSON-LD。

从每个未达标的 check 生成一条建议。命中合规红线的操作会置 compliance_flag。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from keeplix.agents.base import Agent
from keeplix.core.config import get_settings

# check_id → (维度, 建议标题, 详情, 严重度)
_ADVICE: dict[str, tuple[str, str, str, str]] = {
    "http_ok": ("technical_crawlability", "确保页面返回 200 且可抓取",
                "检查服务器状态码、robots 是否放行 AI 爬虫。", "high"),
    "ssr_content_visible": ("technical_crawlability", "让正文在无 JS 时可见（SSR/静态）",
                            "AI 爬虫多不执行 JS，关键内容需服务端渲染或静态输出。", "high"),
    "has_title": ("technical_crawlability", "补全页面 title",
                  "title 是引擎理解页面主题的首要信号。", "medium"),
    "direct_answer_lead": ("content_structure", "开头直接给出答案",
                           "首段用 40–200 字直接回答核心问题，利于被摘录引用。", "high"),
    "heading_hierarchy": ("content_structure", "建立 H1/H2 层级",
                          "用清晰的 heading 层级组织内容，便于结构化提取。", "medium"),
    "qa_or_list_format": ("content_structure", "使用问答/列表/表格",
                          "结构化格式显著提升可提取性与引用率。", "medium"),
    "paragraph_length": ("content_structure", "控制段落长度",
                         "段落保持精炼（≤300 字），提升可摘录性。", "low"),
    "has_author": ("authority_eeat", "标注作者与资质",
                   "补作者 bio 与资质，增强 E-E-A-T 权威信号。", "medium"),
    "has_outbound_citations": ("authority_eeat", "引用权威来源",
                               "引用可溯源的权威来源，提升可信度。", "medium"),
    "has_date": ("freshness", "标注发布/更新日期",
                 "明确时间戳，帮助引擎判断时效。", "medium"),
    "recent_signal": ("freshness", "保持内容新鲜",
                      "核心页面按季度刷新，更新统计与案例。", "low"),
    "extractable_facts": ("citation_friendliness", "加入可提取的事实句",
                          "用独立、含数据的陈述句，利于被直接引用。", "medium"),
    "data_expression": ("citation_friendliness", "数据化表达",
                        "用具体数字/百分比替代模糊表述。", "low"),
    "has_jsonld": ("entity_alignment", "添加 Schema JSON-LD",
                   "用结构化标注声明实体，帮助引擎对齐知识图谱。", "medium"),
    "entity_named": ("entity_alignment", "明确站点/组织实体",
                     "补 og:site_name 与 Organization 标注。", "low"),
    "links_to_preferred_sources": ("walled_garden_presence", "在该引擎偏好平台建立存在感",
                                   "针对目标引擎，布局其偏好的信源平台（如百家号/知乎/抖音）。",
                                   "medium"),
}


@dataclass
class RecommendationItem:
    dimension: str
    title: str
    detail: str
    severity: str
    jsonld: dict | None = None
    compliance_flag: bool = False
    generated_content: str | None = None  # 新增：LLM 生成的现成内容（可直接用）


@dataclass
class RecommendationInput:
    url: str
    breakdown: dict
    brand_name: str | None = None
    first_paragraph: str | None = None  # 新增：用于生成首段直答


@dataclass
class RecommendationOutput:
    items: list[RecommendationItem] = field(default_factory=list)


def _org_jsonld(brand_name: str, url: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand_name,
        "url": url,
    }


# 可以用 LLM 生成内容的 check（内容类建议）
_CONTENT_GENERATABLE = {
    "direct_answer_lead",      # 生成首段直答
    "faq_coverage",             # 生成 FAQ
    "has_author",               # 生成作者 bio
}


async def _generate_content(
    check_id: str, url: str, brand_name: str, first_para: str
) -> str | None:
    """用 LLM 为内容类建议生成现成可用的文本（客户可直接复制粘贴）。"""
    if check_id not in _CONTENT_GENERATABLE:
        return None

    settings = get_settings()
    if not settings.deepseek_api_key:
        return None  # 无 key 时不生成

    prompts = {
        "direct_answer_lead": f"""你是 GEO 优化专家。请为网站 {url}（品牌：{brand_name}）生成一段 40-200 字的"首段直答"。
要求：
- 开门见山回答用户核心问题（"这是什么？""能帮我什么？"）
- 语气专业、简洁，适合被 AI 引用
- 不要废话，不要营销腔

当前首段：{first_para or '（无）'}

请直接输出优化后的首段，不要加解释。""",
        "faq_coverage": f"""你是 GEO 优化专家。请为网站 {url}（品牌：{brand_name}）生成 3-5 个常见问题（FAQ）。
要求：
- 问题要具体、用户会真实搜索
- 答案要直接、40-80 字
- 适合做成结构化 FAQPage

格式：
Q: 问题1
A: 答案1

Q: 问题2
A: 答案2

请直接输出，不要加解释。""",
        "has_author": f"""你是 GEO 优化专家。请为网站 {url}（品牌：{brand_name}）生成一段作者介绍（author bio）。
要求：
- 50-100 字
- 突出专业资质、经验
- 增强 E-E-A-T 权威信号

请直接输出作者介绍，不要加解释。""",
    }

    prompt = prompts.get(check_id)
    if not prompt:
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt.strip()}],
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None  # 生成失败时静默返回 None（不影响主流程）


class RecommendationAgent(Agent[RecommendationInput, RecommendationOutput]):
    name = "recommendation"

    async def run(self, payload: RecommendationInput) -> RecommendationOutput:
        items: list[RecommendationItem] = []
        for _dim, dim_data in payload.breakdown.items():
            for check in dim_data.get("checks", []):
                if check.get("got", 0) >= 1.0:
                    continue  # 已达标
                advice = _ADVICE.get(check["id"])
                if advice is None:
                    continue
                dimension, title, detail, severity = advice
                jsonld = None
                if check["id"] == "has_jsonld" and payload.brand_name:
                    jsonld = _org_jsonld(payload.brand_name, payload.url)

                # 内容生成：为内容类建议生成现成可用的文本
                generated = None
                if check["id"] in _CONTENT_GENERATABLE and payload.brand_name:
                    generated = await _generate_content(
                        check["id"],
                        payload.url,
                        payload.brand_name,
                        payload.first_paragraph or "",
                    )

                items.append(
                    RecommendationItem(
                        dimension=dimension,
                        title=title,
                        detail=detail,
                        severity=severity,
                        jsonld=jsonld,
                        generated_content=generated,
                    )
                )

        # 严重度排序：high > medium > low
        order = {"high": 0, "medium": 1, "low": 2}
        items.sort(key=lambda x: order.get(x.severity, 3))
        return RecommendationOutput(items=items)
