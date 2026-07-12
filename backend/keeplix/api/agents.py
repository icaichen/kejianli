"""Project Agent policy, planning, approval, and execution routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keeplix.core.db import get_session
from keeplix.schemas import (
    AgentPolicyDTO,
    AgentPolicyUpdate,
    AgentRunCreate,
    AgentRunDecision,
    AgentRunDTO,
)
from keeplix.services.agent_service import (
    decide_agent_run,
    execute_agent_run,
    get_agent_policy,
    plan_agent_run,
    update_agent_policy,
)

router = APIRouter(tags=["agents"])


@router.get("/projects/{project_id}/agent-policy", response_model=AgentPolicyDTO | None)
def policy(project_id: str, session: Session = Depends(get_session)) -> AgentPolicyDTO | None:
    return get_agent_policy(project_id, session)


@router.put("/projects/{project_id}/agent-policy", response_model=AgentPolicyDTO)
def save_policy(
    project_id: str,
    req: AgentPolicyUpdate,
    session: Session = Depends(get_session),
) -> AgentPolicyDTO:
    try:
        return update_agent_policy(project_id, req, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/projects/{project_id}/agent-runs", response_model=AgentRunDTO)
def create_run(
    project_id: str,
    req: AgentRunCreate,
    session: Session = Depends(get_session),
) -> AgentRunDTO:
    try:
        return plan_agent_run(project_id, req, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.patch("/projects/{project_id}/agent-runs/{run_id}", response_model=AgentRunDTO)
def decide_run(
    project_id: str,
    run_id: str,
    req: AgentRunDecision,
    session: Session = Depends(get_session),
) -> AgentRunDTO:
    try:
        return decide_agent_run(project_id, run_id, req.decision, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/projects/{project_id}/agent-runs/{run_id}/execute", response_model=AgentRunDTO)
async def execute_run(
    project_id: str,
    run_id: str,
    session: Session = Depends(get_session),
) -> AgentRunDTO:
    try:
        return await execute_agent_run(project_id, run_id, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
