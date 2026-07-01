"""
app/routers/alignment_router.py
POST /project/{project_id}/alignment
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body

from app.models.domain import Project
from app.schemas.schemas import AlignmentResponse, ErrorResponse
from app.services.alignment_service import compute_alignment_score

router = APIRouter(prefix="/project", tags=["Alignment Score"])


@router.post(
    "/{project_id}/alignment",
    response_model=AlignmentResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Compute Client Alignment Score",
)
async def get_alignment_score(
    project_id: str,
    project: Project = Body(...),
) -> AlignmentResponse:
    """
    Layer 2: Semantic alignment between project tasks and
    client requirements using in-memory semantic similarity.
    """
    if project.id != project_id:
        raise HTTPException(status_code=400, detail="project_id mismatch")

    result = await compute_alignment_score(project)
    return AlignmentResponse(data=result)
