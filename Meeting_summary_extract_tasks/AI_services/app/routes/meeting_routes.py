import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from AI_services.app.database.session import get_db
from AI_services.app.models.models import Meeting, Employee, MeetingStatus, Transcript
from AI_services.app.schemas.schemas import MeetingCreate, MeetingOut, MeetingEndIn
from AI_services.app.utils.auth import get_current_employee
from AI_services.app.pipelines.meeting_end_pipeline import meeting_end_pipeline
from AI_services.app.database.redis_client import publish

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meeting", tags=["Meeting"])


@router.post("/start", response_model=MeetingOut, status_code=201)
async def start_meeting(
    body: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    """
    Create and start a new meeting.
    Host is automatically added as an attendee.
    """
    meeting = Meeting(
        title=body.title,
        host_id=current_employee.id,
        language=body.language,
        status=MeetingStatus.PENDING,
        started_at=datetime.utcnow(),
    )
    db.add(meeting)
    await db.flush()

    attendee_ids = list(set(body.attendee_ids + [current_employee.id]))
    for eid in attendee_ids:
        emp = await db.get(Employee, eid)
        if emp:
            meeting.attendees.append(emp)

    await db.commit()
    await db.refresh(meeting)

    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.attendees))
        .where(Meeting.id == meeting.id)
    )
    meeting = result.scalar_one()

    logger.info(f"Meeting started: {meeting.id} by {current_employee.name}")
    return meeting


@router.post("/end", status_code=202)
async def end_meeting(
    body: MeetingEndIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    """
    Signal meeting end. Triggers:
    1. Task extraction
    2. Meeting summarization
    3. Dashboard delivery
    All async in background.
    """
    result = await db.execute(select(Meeting).where(Meeting.id == body.meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.host_id != current_employee.id:
        raise HTTPException(status_code=403, detail="Only the host can end the meeting")
    if meeting.status == MeetingStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Meeting already completed")

    await publish(f"meeting:end:{body.meeting_id}", {"meeting_id": body.meeting_id})

    return {"status": "accepted", "meeting_id": body.meeting_id, "message": "Pipeline started"}


@router.get("/{meeting_id}", response_model=MeetingOut)
async def get_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.attendees))
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.get("/", response_model=list[MeetingOut])
async def list_meetings(
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.attendees))
        .where(Meeting.host_id == current_employee.id)
        .order_by(Meeting.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/{meeting_id}/transcript")
async def get_transcript(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    result = await db.execute(
        select(Transcript).where(Transcript.meeting_id == meeting_id)
    )
    transcript = result.scalar_one_or_none()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {
        "id": transcript.id,
        "meeting_id": transcript.meeting_id,
        "full_text_en": transcript.full_text_en,
        "full_text_ar": transcript.full_text_ar,
        "utterances": transcript.utterances,
        "word_count": transcript.word_count,
        "updated_at": transcript.updated_at,
    }
