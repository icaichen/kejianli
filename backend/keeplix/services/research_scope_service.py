"""研究 Brief 的完整性与正式测量闸门。"""

from __future__ import annotations

from sqlmodel import Session, select

from keeplix.models import BrandEntity, Project

BRIEF_FIELD_LABELS = {
    "brand_name": "核心品牌",
    "market": "研究市场",
    "category": "明确品类",
    "competitors": "主要竞品",
    "research_objective": "研究目标",
}


def research_brief_missing_fields(
    project: Project,
    brand: BrandEntity | None,
) -> list[str]:
    """返回会让市场研究口径失真的缺失字段。"""

    values = {
        "brand_name": brand.brand_name.strip() if brand else project.name.strip(),
        "market": project.market.strip(),
        "category": project.category.strip(),
        "competitors": brand.competitors if brand else [],
        "research_objective": project.research_objective.strip(),
    }
    return [field for field in BRIEF_FIELD_LABELS if not values[field]]


def project_research_readiness(
    project_id: str,
    session: Session,
) -> tuple[Project | None, BrandEntity | None, list[str]]:
    project = session.get(Project, project_id)
    if project is None:
        return None, None, []
    brand = session.exec(
        select(BrandEntity).where(BrandEntity.project_id == project_id)
    ).first()
    return project, brand, research_brief_missing_fields(project, brand)


def incomplete_brief_message(missing_fields: list[str]) -> str:
    labels = "、".join(BRIEF_FIELD_LABELS[field] for field in missing_fields)
    return f"研究 Brief 不完整：请先补齐{labels}，再建立正式基线。"
