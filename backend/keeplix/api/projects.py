"""/api/projects —— 创建/列出项目。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from keeplix.core.db import get_session
from keeplix.schemas import ProjectCreate, ProjectResponse
from keeplix.services.project_service import create_project, list_projects

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectResponse)
def create(req: ProjectCreate, session: Session = Depends(get_session)) -> ProjectResponse:
    return create_project(req, session)


@router.get("/projects", response_model=list[ProjectResponse])
def index(session: Session = Depends(get_session)) -> list[ProjectResponse]:
    return list_projects(session)
