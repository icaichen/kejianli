"""根据企业研究 brief 生成可复用、可编辑的问题框架。"""

from __future__ import annotations

from sqlmodel import Session, select

from keeplix.engines.prompt_quality import classify_prompt, summarize_prompt_quality
from keeplix.models import BrandEntity, Project
from keeplix.schemas import ResearchQuestionFrameworkDTO, ResearchQuestionItemDTO

_RATIONALES = {
    "branded": "了解 AI 如何定义品牌、解释优势与推荐场景。",
    "category": "建立品类品牌地图、选择标准与市场趋势。",
    "problem": "覆盖消费者或采购者从需求出发的真实问题。",
    "comparison": "测量品牌与竞品在直接比较中的位置。",
}


def build_research_question_framework(
    project_id: str, session: Session
) -> ResearchQuestionFrameworkDTO | None:
    project = session.get(Project, project_id)
    if project is None:
        return None
    brand = session.exec(
        select(BrandEntity).where(BrandEntity.project_id == project_id)
    ).first()
    brand_name = brand.brand_name if brand else project.name
    competitors = brand.competitors if brand else []
    market = project.market or "目标市场"
    category = project.category or "目标品类"
    category_product = (
        category
        if category.endswith(("产品", "服务", "软件", "平台"))
        else f"{category}产品"
    )
    first_competitor = competitors[0] if competitors else "主要竞品"
    second_competitor = competitors[1] if len(competitors) > 1 else "其他主要品牌"
    questions = [
        ("branded", f"{brand_name}在{market}{category}市场主要面向哪些人群？"),
        ("branded", f"消费者选择{brand_name}的主要理由有哪些？"),
        ("branded", f"{brand_name}在{category}中的核心优势与局限有哪些？"),
        ("branded", f"AI 通常在什么场景下推荐{brand_name}？"),
        ("category", f"{market}{category}有哪些值得考虑的品牌？"),
        ("category", f"{category}市场的主要品牌梯队分别是什么？"),
        ("category", f"消费者选择{category}时最看重哪些因素？"),
        ("category", f"{market}{category}正在出现哪些消费趋势与购买标准？"),
        ("problem", f"如何选择适合不同需求的{category_product}？"),
        ("problem", f"为什么消费者会更换正在使用的{category}品牌？"),
        ("problem", f"如何判断{category_product}是否值得长期购买？"),
        ("problem", f"怎么避免购买{category}时常见的选择错误？"),
        ("comparison", f"{brand_name}与{first_competitor}相比有什么区别？"),
        ("comparison", f"{brand_name}与{second_competitor}相比各自适合什么需求？"),
        ("comparison", f"{first_competitor}和{second_competitor}哪个好？"),
        ("comparison", f"比较{category}主要品牌时，{brand_name}处于什么位置？"),
    ]
    items = [
        ResearchQuestionItemDTO(
            id=f"{expected_intent}-{index}",
            intent=classify_prompt(text, brand_name, brand.aliases if brand else []).value,
            text=text,
            rationale=_RATIONALES[expected_intent],
            selected=(index - 1) % 4 < 3,
        )
        for index, (expected_intent, text) in enumerate(questions, start=1)
    ]
    prompts = [item.text for item in items if item.selected]
    objective = project.research_objective.strip()
    summary = (
        f"围绕 {market} · {category} · {brand_name}，覆盖品牌、品类、需求和比较四类研究意图。"
        + (f" 研究目标：{objective}" if objective else "")
    )
    return ResearchQuestionFrameworkDTO(
        project_id=project.id,
        title=f"{brand_name} · {category} AI 市场问题框架",
        summary=summary,
        items=items,
        measurement_quality=summarize_prompt_quality(
            prompts, brand_name, brand.aliases if brand else []
        ),
    )
