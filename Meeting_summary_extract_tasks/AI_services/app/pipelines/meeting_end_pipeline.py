"""
MeetingEndPipeline: orchestrates the post-meeting processing in strict order:
  1. Aggregate full transcript from Redis
  2. Translate full transcript to Arabic
  3. Persist Transcript record
  4. Extract tasks (MUST complete before summarization)
  5. Resolve assignees and push tasks to employee dashboards via WebSocket
  6. Summarize meeting
  7. Push summary to all attendees via WebSocket
  8. Mark meeting as COMPLETED
"""
import asyncio
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from AI_services.app.models.models import Meeting, Transcript, Employee, MeetingStatus
from AI_services.app.services.task_extraction_service import task_extraction_service
from AI_services.app.services.summarization_service import summarization_service
from AI_services.app.realtime.translator import TranslationPipeline
from AI_services.app.database.redis_client import get_list, get_value
from AI_services.app.websocket.manager import manager

logger = logging.getLogger(__name__)


class MeetingEndPipeline:

    async def run(self, meeting_id: str, db: AsyncSession):
        logger.info(f"[Pipeline] Starting end pipeline for meeting {meeting_id}")

        result = await db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        meeting = result.scalar_one_or_none()
        if not meeting:
            logger.error(f"[Pipeline] Meeting {meeting_id} not found")
            return

        meeting.status = MeetingStatus.ACTIVE
        await db.flush()

        attendees = meeting.attendees

        # ── Step 1: aggregate transcript from Redis ───────────────────────────
        utterances = await get_list(f"transcript:{meeting_id}:utterances")
        full_text_en = await get_value(f"transcript:{meeting_id}:full_en") or ""

        if not full_text_en and utterances:
            full_text_en = " ".join(u.get("text", "") for u in utterances)

        logger.info(f"[Pipeline] Transcript: {len(full_text_en)} chars, {len(utterances)} utterances")

        # ── Step 2: translate to Arabic ───────────────────────────────────────
        translator = TranslationPipeline(meeting_id)
        full_text_ar = await translator.translate_full_transcript(full_text_en)

        # ── Step 3: persist Transcript ────────────────────────────────────────
        existing = await db.execute(
            select(Transcript).where(Transcript.meeting_id == meeting_id)
        )
        transcript_row = existing.scalar_one_or_none()
        if transcript_row:
            transcript_row.full_text_en = full_text_en
            transcript_row.full_text_ar = full_text_ar
            transcript_row.utterances = utterances
            transcript_row.word_count = len(full_text_en.split())
        else:
            transcript_row = Transcript(
                meeting_id=meeting_id,
                full_text_en=full_text_en,
                full_text_ar=full_text_ar,
                utterances=utterances,
                word_count=len(full_text_en.split()),
            )
            db.add(transcript_row)
        await db.flush()

        # ── Step 4: task extraction (MUST precede summarization) ──────────────
        logger.info(f"[Pipeline] Extracting tasks...")
        tasks = await task_extraction_service.extract_tasks(
            transcript=full_text_en,
            meeting=meeting,
            employees=attendees,
            db=db,
        )
        await db.flush()
        logger.info(f"[Pipeline] {len(tasks)} tasks extracted")

        # ── Step 5: push tasks to employee dashboards ─────────────────────────
        for task in tasks:
            task_payload = {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "status": task.status,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "estimated_hours": task.estimated_hours,
                "category": task.category,
                "meeting_id": meeting_id,
                "meeting_title": meeting.title,
                "source_quote": task.source_quote,
            }
            if task.assignee_id:
                await manager.send_to_employee(task.assignee_id, "task_extracted", task_payload)
                logger.info(f"[Pipeline] Task '{task.title}' pushed to employee {task.assignee_id}")

        # ── Step 6: summarize (after tasks) ───────────────────────────────────
        logger.info(f"[Pipeline] Summarizing meeting...")
        summary = await summarization_service.summarize(
            transcript=full_text_en,
            meeting=meeting,
            attendees=attendees,
            db=db,
        )
        await db.flush()

        # ── Step 7: push summary to ALL attendees ─────────────────────────────
        summary_payload = {
            "id": summary.id,
            "meeting_id": meeting_id,
            "meeting_title": meeting.title,
            "overview": summary.overview,
            "key_points": summary.key_points,
            "decisions": summary.decisions,
            "blockers": summary.blockers,
            "next_steps": summary.next_steps,
            "action_items": summary.action_items,
            "full_text_ar": full_text_ar[:3000],
        }
        await manager.broadcast_to_meeting(meeting_id, "summary_ready", summary_payload)

        # ── Step 8: mark meeting completed ────────────────────────────────────
        meeting.status = MeetingStatus.COMPLETED
        meeting.ended_at = datetime.utcnow()
        await db.commit()

        await manager.broadcast_to_meeting(meeting_id, "meeting_ended", {
            "meeting_id": meeting_id,
            "tasks_count": len(tasks),
        })

        logger.info(f"[Pipeline] Meeting {meeting_id} completed. Tasks: {len(tasks)}")


meeting_end_pipeline = MeetingEndPipeline()
