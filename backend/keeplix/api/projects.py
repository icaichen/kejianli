"""/api/projects —— 创建/列出项目。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keeplix.core.db import get_session
from keeplix.schemas import (
    ArtifactExportResponse,
    ArtifactRevisionCreate,
    ArtifactStatusUpdate,
    CycleVerificationResponse,
    DeliveryRecordCreate,
    DeliveryRecordDTO,
    DueTrackingResponse,
    OptimizationArtifactDTO,
    ProjectCreate,
    ProjectDashboard,
    ProjectResponse,
    PromptSetCreate,
    PromptSetResponse,
    PromptSetVersionCreate,
    TrackingExecutionResponse,
    TrackingPlanCreate,
    TrackingPlanResponse,
    WorkItemDetail,
    WorkItemDTO,
    WorkItemUpdate,
)
from keeplix.services.project_service import (
    create_artifact_revision,
    create_delivery_record,
    create_project,
    create_prompt_set,
    create_prompt_set_version,
    create_tracking_plan,
    create_work_item_from_diagnosis,
    execute_tracking_plan,
    export_artifact,
    get_project_dashboard,
    get_work_item_detail,
    list_projects,
    list_prompt_sets,
    list_tracking_plans,
    run_due_tracking_plans,
    update_artifact_status,
    update_work_item,
    verify_geo_cycle,
)

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectResponse)
def create(req: ProjectCreate, session: Session = Depends(get_session)) -> ProjectResponse:
    return create_project(req, session)


@router.get("/projects", response_model=list[ProjectResponse])
def index(session: Session = Depends(get_session)) -> list[ProjectResponse]:
    return list_projects(session)


@router.get("/projects/{project_id}", response_model=ProjectDashboard)
def detail(project_id: str, session: Session = Depends(get_session)) -> ProjectDashboard:
    dashboard = get_project_dashboard(project_id, session)
    if dashboard is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return dashboard


@router.get("/projects/{project_id}/prompt-sets", response_model=list[PromptSetResponse])
def prompt_sets(
    project_id: str,
    session: Session = Depends(get_session),
) -> list[PromptSetResponse]:
    return list_prompt_sets(project_id, session)


@router.post("/projects/{project_id}/prompt-sets", response_model=PromptSetResponse)
def create_prompt_set_route(
    project_id: str,
    req: PromptSetCreate,
    session: Session = Depends(get_session),
) -> PromptSetResponse:
    try:
        return create_prompt_set(project_id, req, session)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/projects/{project_id}/prompt-sets/{prompt_set_id}/versions",
    response_model=PromptSetResponse,
)
def create_prompt_set_version_route(
    project_id: str,
    prompt_set_id: str,
    req: PromptSetVersionCreate,
    session: Session = Depends(get_session),
) -> PromptSetResponse:
    try:
        return create_prompt_set_version(project_id, prompt_set_id, req, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/projects/{project_id}/tracking-plans", response_model=list[TrackingPlanResponse])
def tracking_plans(
    project_id: str,
    session: Session = Depends(get_session),
) -> list[TrackingPlanResponse]:
    return list_tracking_plans(project_id, session)


@router.post("/projects/{project_id}/tracking-plans", response_model=TrackingPlanResponse)
def create_tracking_plan_route(
    project_id: str,
    req: TrackingPlanCreate,
    session: Session = Depends(get_session),
) -> TrackingPlanResponse:
    try:
        return create_tracking_plan(project_id, req, session)
    except ValueError as error:
        status_code = 404 if "不存在" in str(error) else 400
        raise HTTPException(status_code=status_code, detail=str(error)) from error


@router.post(
    "/projects/{project_id}/tracking-plans/{plan_id}/run",
    response_model=TrackingExecutionResponse,
)
async def run_tracking_plan_route(
    project_id: str,
    plan_id: str,
    session: Session = Depends(get_session),
) -> TrackingExecutionResponse:
    try:
        return await execute_tracking_plan(project_id, plan_id, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/tracking/run-due", response_model=DueTrackingResponse)
async def run_due_tracking_route(
    session: Session = Depends(get_session),
) -> DueTrackingResponse:
    return await run_due_tracking_plans(session)


@router.patch("/projects/{project_id}/work-items/{work_item_id}", response_model=WorkItemDTO)
def update_work_item_route(
    project_id: str,
    work_item_id: str,
    req: WorkItemUpdate,
    session: Session = Depends(get_session),
) -> WorkItemDTO:
    try:
        return update_work_item(project_id, work_item_id, req, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post(
    "/projects/{project_id}/diagnosis/{diagnosis_id}/work-items",
    response_model=WorkItemDTO,
)
def create_work_item_from_diagnosis_route(
    project_id: str,
    diagnosis_id: str,
    session: Session = Depends(get_session),
) -> WorkItemDTO:
    try:
        return create_work_item_from_diagnosis(project_id, diagnosis_id, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post(
    "/projects/{project_id}/cycles/{cycle_id}/verify",
    response_model=CycleVerificationResponse,
)
async def verify_geo_cycle_route(
    project_id: str,
    cycle_id: str,
    session: Session = Depends(get_session),
) -> CycleVerificationResponse:
    try:
        return await verify_geo_cycle(project_id, cycle_id, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/projects/{project_id}/work-items/{work_item_id}", response_model=WorkItemDetail)
def work_item_detail_route(
    project_id: str,
    work_item_id: str,
    session: Session = Depends(get_session),
) -> WorkItemDetail:
    try:
        return get_work_item_detail(project_id, work_item_id, session)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/projects/{project_id}/work-items/{work_item_id}/artifacts",
    response_model=OptimizationArtifactDTO,
)
def create_artifact_revision_route(
    project_id: str,
    work_item_id: str,
    req: ArtifactRevisionCreate,
    session: Session = Depends(get_session),
) -> OptimizationArtifactDTO:
    try:
        return create_artifact_revision(project_id, work_item_id, req, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.patch(
    "/projects/{project_id}/artifacts/{artifact_id}",
    response_model=OptimizationArtifactDTO,
)
def update_artifact_status_route(
    project_id: str,
    artifact_id: str,
    req: ArtifactStatusUpdate,
    session: Session = Depends(get_session),
) -> OptimizationArtifactDTO:
    try:
        return update_artifact_status(project_id, artifact_id, req, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post(
    "/projects/{project_id}/artifacts/{artifact_id}/export",
    response_model=ArtifactExportResponse,
)
def export_artifact_route(
    project_id: str,
    artifact_id: str,
    session: Session = Depends(get_session),
) -> ArtifactExportResponse:
    try:
        return export_artifact(project_id, artifact_id, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post(
    "/projects/{project_id}/artifacts/{artifact_id}/deliveries",
    response_model=DeliveryRecordDTO,
)
def create_delivery_record_route(
    project_id: str,
    artifact_id: str,
    req: DeliveryRecordCreate,
    session: Session = Depends(get_session),
) -> DeliveryRecordDTO:
    try:
        return create_delivery_record(project_id, artifact_id, req, session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
