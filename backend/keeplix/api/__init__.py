"""路由层：请求校验 + 调 service + 返回 DTO。加 endpoint 见 AGENTS.md。"""

from fastapi import APIRouter

from keeplix.api import analyses, citations, engagements, engines, projects

api_router = APIRouter(prefix="/api")
api_router.include_router(projects.router)
api_router.include_router(analyses.router)
api_router.include_router(citations.router)
api_router.include_router(engagements.router)
api_router.include_router(engines.router)

__all__ = ["api_router"]
