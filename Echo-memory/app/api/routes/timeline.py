import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.memory import MemoryType
from app.schemas.memory import MemoryOut
from app.schemas.timeline import TimelineResponse
from app.services.memory_service import MemoryService

router = APIRouter(tags=["Timeline"])


@router.get(
    "/project/{project_id}/timeline",
    response_model=TimelineResponse,
    summary="Chronological memory timeline for a project",
)
def get_project_timeline(
    project_id: uuid.UUID,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    memory_type: Optional[MemoryType] = Query(default=None),
    team_name: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> TimelineResponse:
    service = MemoryService(db)
    memories = service.get_timeline(
        project_id, limit=limit, offset=offset, memory_type=memory_type, team_name=team_name
    )
    return TimelineResponse(
        project_id=project_id,
        total=len(memories),
        items=[MemoryOut.model_validate(m) for m in memories],
    )
