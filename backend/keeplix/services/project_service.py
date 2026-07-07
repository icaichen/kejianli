"""项目编排：创建/列出项目（自动补 default org + client）。"""

from __future__ import annotations

from sqlmodel import Session, select

from keeplix.models import Client, Organization, Project
from keeplix.schemas import ProjectCreate, ProjectResponse

_DEFAULT_ORG = "keeplix-default-org"


def _ensure_default_org(session: Session) -> Organization:
    org = session.get(Organization, _DEFAULT_ORG)
    if org is None:
        org = Organization(id=_DEFAULT_ORG, name="keeplix")
        session.add(org)
        session.flush()
    return org


def create_project(req: ProjectCreate, session: Session) -> ProjectResponse:
    org = _ensure_default_org(session)

    client = session.exec(
        select(Client).where(Client.org_id == org.id, Client.name == req.client_name)
    ).first()
    if client is None:
        client = Client(org_id=org.id, name=req.client_name)
        session.add(client)
        session.flush()

    project = Project(
        client_id=client.id,
        name=req.name,
        primary_domain=req.primary_domain,
        locale=req.locale,
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    return ProjectResponse(
        id=project.id, name=project.name, primary_domain=project.primary_domain,
        locale=project.locale, status=project.status,
    )


def list_projects(session: Session) -> list[ProjectResponse]:
    projects = session.exec(select(Project)).all()
    return [
        ProjectResponse(
            id=p.id, name=p.name, primary_domain=p.primary_domain,
            locale=p.locale, status=p.status,
        )
        for p in projects
    ]
