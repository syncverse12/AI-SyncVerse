"""
migration_guide.py
==================
Drop-in HTTP client for the main backend to call both microservices.

Replace the direct function calls to:
  task_extraction_service.extract_tasks(...)
  summarization_service.summarize(...)

with calls to:
  MicroserviceClient.extract_tasks(...)
  MicroserviceClient.generate_summary(...)

Install: pip install httpx
"""
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

# ── Configure these URLs after deploying to Hugging Face Spaces ───────────────

TASK_EXTRACTION_URL = "https://<your-username>-meeting-task-extraction.hf.space"
SUMMARY_URL         = "https://<your-username>-meeting-summary-service.hf.space"

# For local development:
# TASK_EXTRACTION_URL = "http://localhost:7860"
# SUMMARY_URL         = "http://localhost:7861"

REQUEST_TIMEOUT = 120.0   # seconds — LLM calls can take 10-30s for long transcripts


# ── Dataclasses matching the microservice response shapes ─────────────────────

class ExtractedTask:
    def __init__(self, data: dict):
        self.title          = data.get("title", "")
        self.description    = data.get("description")
        self.assignee       = data.get("assignee")
        self.deadline       = data.get("deadline")
        self.priority       = data.get("priority", "MEDIUM")
        self.category       = data.get("category", "general")
        self.estimated_hours = data.get("estimated_hours")
        self.source_quote   = data.get("source_quote")
        self.confidence     = data.get("confidence", 0.9)

    def to_db_dict(self) -> dict:
        """Convert to a dict suitable for your ORM / DB insert."""
        return {
            "title":           self.title,
            "description":     self.description,
            "assignee_raw":    self.assignee,
            "deadline":        self.deadline,
            "priority":        self.priority,
            "category":        self.category,
            "estimated_hours": self.estimated_hours,
            "source_quote":    self.source_quote,
        }


class MeetingSummary:
    def __init__(self, data: dict):
        self.meeting_id   = data.get("meeting_id")
        self.meeting_title = data.get("meeting_title", "")
        self.summary      = data.get("summary", "")
        self.key_points   = data.get("key_points", [])
        self.decisions    = data.get("decisions", [])
        self.risks        = data.get("risks", [])
        self.next_steps   = data.get("next_steps", [])
        self.action_items = data.get("action_items", [])
        self.full_markdown = data.get("full_markdown")


# ── Client ────────────────────────────────────────────────────────────────────

class MicroserviceClient:
    """
    Async HTTP client wrapping both AI microservices.
    Use one shared instance per application (or per request — both are stateless).
    """

    def __init__(
        self,
        task_extraction_base_url: str = TASK_EXTRACTION_URL,
        summary_base_url: str = SUMMARY_URL,
        timeout: float = REQUEST_TIMEOUT,
    ):
        self._task_url    = task_extraction_base_url.rstrip("/")
        self._summary_url = summary_base_url.rstrip("/")
        self._timeout     = timeout

    async def extract_tasks(
        self,
        meeting_id: int | str,
        transcript: str,
        attendees: Optional[list[str]] = None,
        meeting_date: Optional[str] = None,
    ) -> list[ExtractedTask]:
        """
        Call the Task Extraction microservice.

        Args:
            meeting_id:   Your internal meeting ID (echoed in response)
            transcript:   Full meeting text (English or Arabic)
            attendees:    Known attendee names for better assignee matching
            meeting_date: YYYY-MM-DD — used to resolve "by Friday" deadlines

        Returns:
            List of ExtractedTask objects

        Raises:
            httpx.HTTPStatusError on non-2xx response
            httpx.TimeoutException if service doesn't respond in time
        """
        payload = {
            "meeting_id":   meeting_id,
            "transcript":   transcript,
            "attendees":    attendees or [],
            "meeting_date": meeting_date,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._task_url}/extract-tasks", json=payload)
            resp.raise_for_status()
            data = resp.json()

        tasks = [ExtractedTask(t) for t in data.get("tasks", [])]
        notes = data.get("processing_notes", [])
        if notes:
            logger.info(f"Task extraction notes for meeting {meeting_id}: {notes}")
        logger.info(
            f"Extracted {len(tasks)} tasks for meeting {meeting_id} "
            f"(raw count: {data.get('tasks_count', '?')})"
        )
        return tasks

    async def generate_summary(
        self,
        meeting_id: int | str,
        transcript: str,
        meeting_title: str = "Team Meeting",
        attendees: Optional[list[str]] = None,
        language: str = "en",
    ) -> MeetingSummary:
        """
        Call the Meeting Summary microservice.

        Args:
            meeting_id:    Your internal meeting ID (echoed in response)
            transcript:    Full meeting text
            meeting_title: Used in the summary header and markdown output
            attendees:     Known attendee names
            language:      Output language — 'en' or 'ar'

        Returns:
            MeetingSummary object

        Raises:
            httpx.HTTPStatusError on non-2xx response
            httpx.TimeoutException if service doesn't respond in time
        """
        payload = {
            "meeting_id":    meeting_id,
            "transcript":    transcript,
            "meeting_title": meeting_title,
            "attendees":     attendees or [],
            "language":      language,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._summary_url}/generate-summary", json=payload)
            resp.raise_for_status()
            data = resp.json()

        logger.info(f"Summary generated for meeting {meeting_id}")
        return MeetingSummary(data)

    async def health_check(self) -> dict:
        """Check both services are reachable and healthy."""
        results = {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for name, url in [
                ("task_extraction", self._task_url),
                ("summary",         self._summary_url),
            ]:
                try:
                    resp = await client.get(f"{url}/health")
                    results[name] = resp.json() if resp.status_code == 200 else {"status": "error", "code": resp.status_code}
                except Exception as e:
                    results[name] = {"status": "unreachable", "error": str(e)}
        return results


# ── Singleton for your app ────────────────────────────────────────────────────

ai_client = MicroserviceClient()


# ══════════════════════════════════════════════════════════════════════════════
# MIGRATION GUIDE
# ══════════════════════════════════════════════════════════════════════════════
#
# BEFORE (monolith — direct function calls inside MeetingEndPipeline):
# ─────────────────────────────────────────────────────────────────────
#
#   from app.services.task_extraction_service import task_extraction_service
#   from app.services.summarization_service import summarization_service
#
#   tasks = await task_extraction_service.extract_tasks(
#       transcript=full_text_en,
#       meeting=meeting,
#       employees=attendees,
#       db=db,
#   )
#
#   summary = await summarization_service.summarize(
#       transcript=full_text_en,
#       meeting=meeting,
#       attendees=attendees,
#       db=db,
#   )
#
#
# AFTER (microservices — HTTP calls via MicroserviceClient):
# ──────────────────────────────────────────────────────────
#
#   from migration_guide import ai_client
#
#   attendee_names = [e.name for e in meeting.attendees]
#
#   # Step 4: Extract tasks (HTTP call to Task Extraction Service)
#   extracted = await ai_client.extract_tasks(
#       meeting_id=meeting.id,
#       transcript=full_text_en,
#       attendees=attendee_names,
#       meeting_date=meeting.started_at.strftime("%Y-%m-%d"),
#   )
#
#   # Save tasks to your DB (same as before, but data comes from HTTP response)
#   for task_data in extracted:
#       assignee_id, _ = await resolve_assignee(task_data.assignee, attendees, db)
#       task = Task(
#           meeting_id=meeting.id,
#           assignee_id=assignee_id,
#           **task_data.to_db_dict(),
#       )
#       db.add(task)
#   await db.flush()
#
#   # Step 6: Summarize (HTTP call to Summary Service)
#   summary_data = await ai_client.generate_summary(
#       meeting_id=meeting.id,
#       transcript=full_text_en,
#       meeting_title=meeting.title,
#       attendees=attendee_names,
#       language="en",
#   )
#
#   # Save summary to your DB (same as before)
#   summary = MeetingSummary(
#       meeting_id=meeting.id,
#       overview=summary_data.summary,
#       key_points=summary_data.key_points,
#       decisions=summary_data.decisions,
#       blockers=summary_data.risks,
#       next_steps=summary_data.next_steps,
#       action_items=summary_data.action_items,
#       full_markdown=summary_data.full_markdown,
#   )
#   db.add(summary)
#   await db.flush()
#
#
# NOTE: assignee_id resolution (matching name → DB employee row) stays in the
# monolith because it requires DB access. The microservice returns `assignee`
# as a raw name string; you call resolve_assignee() locally exactly as before.
#
# The pipeline ORDER is unchanged:
#   [4] extract_tasks  →  now HTTP POST /extract-tasks
#   [5] push tasks to employee dashboards  →  unchanged (WebSocket in monolith)
#   [6] generate_summary  →  now HTTP POST /generate-summary
#   [7] push summary to all attendees  →  unchanged (WebSocket in monolith)
#
# ══════════════════════════════════════════════════════════════════════════════
