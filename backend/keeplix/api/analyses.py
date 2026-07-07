"""POST /api/analyses —— URL → GEO 分数 + 建议。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from keeplix.core.db import get_session
from keeplix.schemas import AnalysisRequest, AnalysisResponse
from keeplix.services.analysis_service import run_analysis

router = APIRouter(tags=["analyses"])


@router.post("/analyses", response_model=AnalysisResponse)
async def create_analysis(
    req: AnalysisRequest, session: Session = Depends(get_session)
) -> AnalysisResponse:
    return await run_analysis(req, session)
