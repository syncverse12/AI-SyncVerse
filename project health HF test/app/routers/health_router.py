"""
app/routers/health_router.py
POST /project/{project_id}/health
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body

from app.models.domain import Project
from app.schemas.schemas import HealthResponse, ErrorResponse
from app.services.health_service import compute_health_score

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
) -> HealthResponse:
    """
    Layer 1: Execution health score based on completion rate,
    goal progress, efficiency, and delay impact.
    """
    if project.id != project_id:
        raise HTTPException(status_code=400, detail="project_id mismatch in path vs body")

    result = compute_health_score(project)
    return HealthResponse(data=result)
