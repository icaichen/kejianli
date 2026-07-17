"""POST /api/citations/run —— 多引擎 citation 采样 → SoV。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keeplix.core.db import get_session
from keeplix.schemas import CitationRunRequest, CitationRunResponse
from keeplix.services.citation_service import run_citations

router = APIRouter(tags=["citations"])


@router.post("/citations/run", response_model=CitationRunResponse)
async def run_citation(
    req: CitationRunRequest, session: Session = Depends(get_session)
) -> CitationRunResponse:
    try:
        return await run_citations(req, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
