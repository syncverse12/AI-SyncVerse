"""
app/routers/alignment_router.py
POST /project/{project_id}/alignment
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Body

from app.models.domain import Project
from app.schemas.schemas import AlignmentResponse, ErrorResponse
from app.services.alignment_service import compute_alignment_score
from app.services.qdrant_service import index_full_project

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
    reindex: bool = Query(False, description="Force re-index into Qdrant before scoring"),
) -> AlignmentResponse:
    """
    Layer 2: Semantic alignment between project deliverables and
    original client requirements using Qdrant vector similarity.
    """
    if project.id != project_id:
        raise HTTPException(status_code=400, detail="project_id mismatch")

    await index_full_project(project, force_reindex=reindex)
    result = await compute_alignment_score(project)
    return AlignmentResponse(data=result)
