"""
app/routers/health_router.py
GET /project/{project_id}/health
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Body

from app.models.domain import Project
from app.schemas.schemas import HealthResponse, ErrorResponse
from app.services.health_service import compute_health_score
from app.services.qdrant_service import index_full_project

router = APIRouter(prefix="/project", tags=["Health Score"])


@router.post(
    "/{project_id}/health",
    response_model=HealthResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Compute Project Health Score",
)
async def get_health_score(
    project_id: str,
    project: Project = Body(...),
    reindex: bool = Query(False, description="Force re-index into Qdrant"),
) -> HealthResponse:
    """
    Layer 1: Execution health score based on completion rate,
    goal progress, efficiency, and delay impact.
    """
    if project.id != project_id:
        raise HTTPException(status_code=400, detail="project_id mismatch in path vs body")

    if reindex:
        await index_full_project(project, force_reindex=True)

    result = compute_health_score(project)
    return HealthResponse(data=result)
