from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from AI_services.app.database.session import get_db
from AI_services.app.models.models import Employee, MeetingSummary, Meeting
from AI_services.app.schemas.schemas import SummaryOut
from AI_services.app.utils.auth import get_current_employee

router = APIRouter(prefix="/meeting", tags=["Summary"])


@router.get("/{meeting_id}/summary", response_model=SummaryOut)
async def get_meeting_summary(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    """
    Get meeting summary. Available to ALL meeting attendees.
    Returns 404 if summary not yet generated (meeting still active).
    """
    meeting_result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = meeting_result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    is_attendee = any(a.id == current_employee.id for a in meeting.attendees)
    is_host = meeting.host_id == current_employee.id
    if not is_attendee and not is_host:
        raise HTTPException(status_code=403, detail="You are not a meeting attendee")

    result = await db.execute(
        select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(
            status_code=404,
            detail="Summary not yet available. Meeting may still be processing."
        )
    return summary


@router.get("/{meeting_id}/tasks")
async def get_meeting_tasks(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    """Get all tasks extracted from a meeting (host view)."""
    from AI_services.app.models.models import Task
    from sqlalchemy import select

    meeting_result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = meeting_result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.host_id != current_employee.id:
        raise HTTPException(status_code=403, detail="Only host can view all meeting tasks")

    result = await db.execute(
        select(Task).where(Task.meeting_id == meeting_id).order_by(Task.created_at)
    )
    tasks = result.scalars().all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "assignee_id": t.assignee_id,
            "assignee_raw": t.assignee_raw,
            "priority": t.priority,
            "status": t.status,
            "deadline": t.deadline,
            "category": t.category,
        }
        for t in tasks
    ]
