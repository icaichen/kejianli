"""POST /api/engagements/run —— 一次完整 GEO 服务交付（分析+建议+可见度→报告）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from keeplix.core.db import get_session
from keeplix.schemas import EngagementRequest, EngagementResponse
from keeplix.services.engagement_service import run_engagement

router = APIRouter(tags=["engagements"])


@router.post("/engagements/run", response_model=EngagementResponse)
async def run(
    req: EngagementRequest, session: Session = Depends(get_session)
) -> EngagementResponse:
    return await run_engagement(req, session)
