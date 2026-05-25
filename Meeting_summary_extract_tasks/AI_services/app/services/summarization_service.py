"""
Meeting summarization service.
Runs AFTER task extraction is complete.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from AI_services.app.utils.llm_client import chat_complete, safe_parse_json
from AI_services.app.prompts.templates import SUMMARIZATION_PROMPT
from AI_services.app.models.models import Meeting, MeetingSummary, Employee

logger = logging.getLogger(__name__)


class SummarizationService:

    async def summarize(
        self,
        transcript: str,
        meeting: Meeting,
        attendees: list[Employee],
        db: AsyncSession,
    ) -> MeetingSummary:
        """
        Generate structured meeting summary from final transcript.
        Always called after task extraction.
        """
        if not transcript.strip():
            logger.warning(f"Empty transcript for summarization: {meeting.id}")
            return await self._empty_summary(meeting, db)

        attendees_str = ", ".join([e.name for e in attendees]) or "Unknown"

        prompt = SUMMARIZATION_PROMPT.format(
            title=meeting.title,
            attendees=attendees_str,
            transcript=transcript[:15000],
        )

        logger.info(f"Summarizing meeting {meeting.id}")
        raw = await chat_complete(prompt, expect_json=True, temperature=0.2, max_tokens=4096)
        parsed = safe_parse_json(raw)

        if not parsed:
            logger.error(f"Summarization failed for meeting {meeting.id}")
            return await self._empty_summary(meeting, db)

        summary = MeetingSummary(
            meeting_id=meeting.id,
            overview=parsed.get("overview", "No overview available."),
            key_points=parsed.get("key_points", []),
            decisions=parsed.get("decisions", []),
            blockers=parsed.get("blockers", []),
            next_steps=parsed.get("next_steps", []),
            action_items=parsed.get("action_items", []),
            full_markdown=parsed.get("full_markdown"),
        )
        db.add(summary)
        await db.flush()

        logger.info(f"Summary saved for meeting {meeting.id}")
        return summary

    async def _empty_summary(self, meeting: Meeting, db: AsyncSession) -> MeetingSummary:
        summary = MeetingSummary(
            meeting_id=meeting.id,
            overview="Summary unavailable — transcript was empty or processing failed.",
            key_points=[],
            decisions=[],
            blockers=[],
            next_steps=[],
            action_items=[],
        )
        db.add(summary)
        await db.flush()
        return summary


summarization_service = SummarizationService()
