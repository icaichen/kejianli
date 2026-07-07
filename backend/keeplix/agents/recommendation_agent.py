"""RecommendationAgent：score breakdown → 可执行建议清单 + Schema JSON-LD。

从每个未达标的 check 生成一条建议。命中合规红线的操作会置 compliance_flag。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from keeplix.agents.base import Agent

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


@dataclass
class RecommendationInput:
    url: str
    breakdown: dict
    brand_name: str | None = None


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
                items.append(
                    RecommendationItem(
                        dimension=dimension, title=title, detail=detail,
                        severity=severity, jsonld=jsonld,
                    )
                )

        # 严重度排序：high > medium > low
        order = {"high": 0, "medium": 1, "low": 2}
        items.sort(key=lambda x: order.get(x.severity, 3))
        return RecommendationOutput(items=items)
