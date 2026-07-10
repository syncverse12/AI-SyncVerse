import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.memory import MemoryOut
from app.schemas.summary import WeeklySummaryResponse
from app.services.summary_service import SummaryService

router = APIRouter(tags=["Summary"])


@router.get(
    "/summary/week",
    response_model=WeeklySummaryResponse,
    summary="Generate a weekly summary of everything that happened on a project",
)
def get_weekly_summary(
    project_id: uuid.UUID = Query(...), db: Session = Depends(get_db)
) -> WeeklySummaryResponse:
    service = SummaryService(db)
    summary_text, highlighted, period_start, period_end, total = service.generate_weekly_summary(project_id)
    return WeeklySummaryResponse(
        project_id=project_id,
        period_start=period_start,
        period_end=period_end,
        summary=summary_text,
        memories_considered=total,
        highlighted_memories=[MemoryOut.model_validate(m) for m in highlighted],
    )
