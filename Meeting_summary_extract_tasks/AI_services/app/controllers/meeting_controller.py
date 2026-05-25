"""
MeetingController separates business logic from route handlers.
Routes call controllers; controllers call services.
"""
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from AI_services.app.models.models import (
    Meeting, Employee, Transcript, Task, MeetingSummary, MeetingStatus
)
from AI_services.app.database.redis_client import get_list, get_value

logger = logging.getLogger(__name__)


class MeetingController:

    async def get_meeting_with_attendees(
        self, meeting_id: str, db: AsyncSession
    ) -> Meeting | None:
        result = await db.execute(
            select(Meeting)
            .options(selectinload(Meeting.attendees))
            .where(Meeting.id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def assert_attendee(self, meeting: Meeting, employee_id: str):
        is_attendee = any(a.id == employee_id for a in meeting.attendees)
        is_host = meeting.host_id == employee_id
        if not is_attendee and not is_host:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Not a meeting attendee")

    async def get_transcript_text(self, meeting_id: str, db: AsyncSession) -> str:
        result = await db.execute(
            select(Transcript).where(Transcript.meeting_id == meeting_id)
        )
        transcript = result.scalar_one_or_none()
        if transcript and transcript.full_text_en:
            return transcript.full_text_en
        full_en = await get_value(f"transcript:{meeting_id}:full_en")
        if full_en:
            return full_en
        utterances = await get_list(f"transcript:{meeting_id}:utterances")
        return " ".join(u.get("text", "") for u in utterances)

    async def get_meeting_stats(self, meeting_id: str, db: AsyncSession) -> dict:
        transcript_result = await db.execute(
            select(Transcript).where(Transcript.meeting_id == meeting_id)
        )
        transcript = transcript_result.scalar_one_or_none()

        tasks_result = await db.execute(
            select(Task).where(Task.meeting_id == meeting_id)
        )
        tasks = tasks_result.scalars().all()

        return {
            "meeting_id": meeting_id,
            "transcript_word_count": transcript.word_count if transcript else 0,
            "tasks_total": len(tasks),
            "tasks_assigned": sum(1 for t in tasks if t.assignee_id),
            "tasks_unassigned": sum(1 for t in tasks if not t.assignee_id),
            "tasks_by_priority": {
                "URGENT": sum(1 for t in tasks if t.priority == "URGENT"),
                "HIGH": sum(1 for t in tasks if t.priority == "HIGH"),
                "MEDIUM": sum(1 for t in tasks if t.priority == "MEDIUM"),
                "LOW": sum(1 for t in tasks if t.priority == "LOW"),
            },
        }


class EmployeeController:

    async def get_employee_task_summary(
        self, employee_id: str, db: AsyncSession
    ) -> dict:
        result = await db.execute(
            select(Task).where(Task.assignee_id == employee_id)
        )
        tasks = result.scalars().all()
        return {
            "employee_id": employee_id,
            "total": len(tasks),
            "todo": sum(1 for t in tasks if t.status == "TODO"),
            "in_progress": sum(1 for t in tasks if t.status == "IN_PROGRESS"),
            "done": sum(1 for t in tasks if t.status == "DONE"),
            "blocked": sum(1 for t in tasks if t.status == "BLOCKED"),
            "urgent": sum(1 for t in tasks if t.priority == "URGENT"),
        }


meeting_controller = MeetingController()
employee_controller = EmployeeController()
