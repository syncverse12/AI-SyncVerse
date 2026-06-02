import logging
from fastapi import APIRouter, HTTPException
from app.schemas.schemas import (
    TaskExtractionRequest,
    TaskExtractionResponse,
    HealthResponse,
)
from app.services.task_extraction_service import task_extraction_service
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return HealthResponse(
        status="healthy",
        service=settings.SERVICE_NAME,
        version=settings.SERVICE_VERSION,
    )


@router.post("/extract-tasks", response_model=TaskExtractionResponse, tags=["Task Extraction"])
async def extract_tasks(body: TaskExtractionRequest):
    """
    Extract actionable tasks from a meeting transcript.

    - Accepts plain text transcript in English or Arabic
    - Returns structured task list with assignee, deadline, priority
    - Completely stateless — no database or cache required
    """
    logger.info(
        f"Extract-tasks request: meeting_id={body.meeting_id}, "
        f"transcript_len={len(body.transcript)}, attendees={body.attendees}"
    )

    try:
        tasks, notes = await task_extraction_service.extract(
            transcript=body.transcript,
            attendees=body.attendees,
            meeting_date=body.meeting_date,
        )
    except Exception as e:
        logger.error(f"Extraction failed for meeting {body.meeting_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Task extraction failed: {str(e)}",
        )

    return TaskExtractionResponse(
        meeting_id=body.meeting_id,
        tasks=tasks,
        tasks_count=len(tasks),
        processing_notes=notes,
    )
