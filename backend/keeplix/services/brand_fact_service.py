"""管理可验证品牌事实，为 Improve 与 Agent 提供可追溯输入。"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlmodel import Session, col, select

from keeplix.models import BrandFact, Project
from keeplix.schemas import BrandFactCreate, BrandFactDTO, BrandFactUpdate


def _fact_dto(fact: BrandFact) -> BrandFactDTO:
    return BrandFactDTO.model_validate(fact, from_attributes=True)


def _validate_source_url(value: str) -> str:
    normalized = value.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("事实来源必须是可访问的 HTTP(S) URL")
    return normalized


def list_brand_facts(project_id: str, session: Session) -> list[BrandFactDTO]:
    if session.get(Project, project_id) is None:
        raise ValueError("项目不存在")
    facts = session.exec(
        select(BrandFact)
        .where(BrandFact.project_id == project_id)
        .order_by(col(BrandFact.updated_at).desc())
    ).all()
    return [_fact_dto(fact) for fact in facts]


def create_brand_fact(
    project_id: str, req: BrandFactCreate, session: Session
) -> BrandFactDTO:
    if session.get(Project, project_id) is None:
        raise ValueError("项目不存在")
    claim = req.claim.strip()
    source_url = _validate_source_url(req.source_url)
    existing = session.exec(
        select(BrandFact).where(
            BrandFact.project_id == project_id,
            BrandFact.claim == claim,
            BrandFact.source_url == source_url,
            BrandFact.status != "rejected",
        )
    ).first()
    if existing:
        return _fact_dto(existing)
    fact = BrandFact(
        project_id=project_id,
        fact_type=req.fact_type,
        claim=claim,
        source_url=source_url,
        status="verified",
    )
    session.add(fact)
    session.commit()
    session.refresh(fact)
    return _fact_dto(fact)


def update_brand_fact(
    project_id: str,
    fact_id: str,
    req: BrandFactUpdate,
    session: Session,
) -> BrandFactDTO:
    fact = session.get(BrandFact, fact_id)
    if fact is None or fact.project_id != project_id:
        raise ValueError("品牌事实不存在")
    if req.fact_type is not None:
        fact.fact_type = req.fact_type
    if req.claim is not None:
        fact.claim = req.claim.strip()
    if req.source_url is not None:
        fact.source_url = _validate_source_url(req.source_url)
    if req.status is not None:
        fact.status = req.status
    fact.updated_at = datetime.now(UTC)
    session.add(fact)
    session.commit()
    session.refresh(fact)
    return _fact_dto(fact)
