import logging
from fastapi import APIRouter, HTTPException
from app.schemas.schemas import SummaryRequest, SummaryResponse, HealthResponse
from app.services.summarization_service import summarization_service
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


@router.post("/generate-summary", response_model=SummaryResponse, tags=["Summarization"])
async def generate_summary(body: SummaryRequest):
    """
    Generate a structured meeting summary from a transcript.

    - Accepts full meeting transcript (English or Arabic)
    - Returns structured summary: overview, key points, decisions, risks, next steps
    - Automatically handles long transcripts via chunking + merge
    - Completely stateless — no database or cache required
    """
    logger.info(
        f"Generate-summary request: meeting_id={body.meeting_id}, "
        f"title={body.meeting_title!r}, transcript_len={len(body.transcript)}, "
        f"attendees={body.attendees}, language={body.language}"
    )

    try:
        result = await summarization_service.summarize(
            transcript=body.transcript,
            meeting_id=body.meeting_id,
            meeting_title=body.meeting_title,
            attendees=body.attendees,
            language=body.language,
        )
    except Exception as e:
        logger.error(f"Summarization failed for meeting {body.meeting_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Summary generation failed: {str(e)}",
        )

    return result
