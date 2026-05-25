"""
Task extraction pipeline.
Uses Groq LLM for task detection + spaCy NER for initial entity spotting.
Includes employee name resolution against the database.
"""
import logging
import re
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except Exception:
    SPACY_AVAILABLE = False
    nlp = None

from AI_services.app.utils.llm_client import chat_complete, safe_parse_json
from AI_services.app.prompts.templates import TASK_EXTRACTION_PROMPT, ASSIGNEE_RESOLUTION_PROMPT
from AI_services.app.models.models import Employee, Task, Meeting
from AI_services.app.schemas.schemas import TaskOut

logger = logging.getLogger(__name__)


# ── Assignee name resolution ──────────────────────────────────────────────────

async def resolve_assignee(
    raw_name: str,
    employees: list[Employee],
    db: AsyncSession,
) -> tuple[Optional[str], Optional[str]]:
    """
    Match raw_name string to a known employee.
    Returns (employee_id, matched_name) or (None, None).
    Uses fuzzy matching first, then LLM as fallback.
    """
    if not raw_name:
        return None, None

    raw_lower = raw_name.lower().strip()

    for emp in employees:
        name_lower = emp.name.lower()
        first = name_lower.split()[0]
        if raw_lower == name_lower or raw_lower == first:
            return emp.id, emp.name
        if raw_lower in name_lower or name_lower in raw_lower:
            return emp.id, emp.name

    if not employees:
        return None, raw_name

    emp_list = "\n".join([f"- id={e.id} name={e.name}" for e in employees])
    prompt = ASSIGNEE_RESOLUTION_PROMPT.format(
        employees=emp_list,
        raw_name=raw_name,
    )
    try:
        raw_result = await chat_complete(prompt, expect_json=True, temperature=0.0)
        result = safe_parse_json(raw_result)
        if result and result.get("confidence", 0) >= 0.7:
            return result.get("matched_id"), result.get("matched_name")
    except Exception as e:
        logger.warning(f"LLM assignee resolution failed: {e}")

    return None, raw_name


# ── NER helper ────────────────────────────────────────────────────────────────

def extract_person_names(text: str) -> list[str]:
    """Use spaCy NER to find PERSON entities in transcript text."""
    if not SPACY_AVAILABLE or nlp is None:
        return []
    doc = nlp(text[:50000])
    return list({ent.text for ent in doc.ents if ent.label_ == "PERSON"})


# ── Deadline parser ───────────────────────────────────────────────────────────

def parse_deadline(raw: Optional[str]) -> Optional[datetime]:
    if not raw or raw.lower() in ("null", "none", ""):
        return None
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


# ── Main extraction service ───────────────────────────────────────────────────

class TaskExtractionService:

    async def extract_tasks(
        self,
        transcript: str,
        meeting: Meeting,
        employees: list[Employee],
        db: AsyncSession,
    ) -> list[Task]:
        """
        Full pipeline:
        1. NER scan to hint at person names in the text
        2. LLM prompt with attendee context → structured task list
        3. Resolve each assignee to a real employee record
        4. Persist Task rows and return them
        """
        if not transcript.strip():
            logger.warning(f"Empty transcript for meeting {meeting.id}")
            return []

        ner_names = extract_person_names(transcript)
        attendee_names = [e.name for e in employees]

        all_names = list(dict.fromkeys(attendee_names + ner_names))
        attendees_str = "\n".join([f"- {name}" for name in all_names]) or "(no named attendees)"

        prompt = TASK_EXTRACTION_PROMPT.format(
            transcript=transcript[:12000],
            attendees=attendees_str,
        )

        logger.info(f"Extracting tasks for meeting {meeting.id} ({len(transcript)} chars)")

        raw = await chat_complete(prompt, expect_json=True, temperature=0.1)
        parsed = safe_parse_json(raw)

        if not parsed or "tasks" not in parsed:
            logger.error(f"Task extraction returned unparseable JSON for meeting {meeting.id}")
            return []

        raw_tasks = parsed["tasks"]
        saved_tasks: list[Task] = []

        for raw_task in raw_tasks:
            if not raw_task.get("title"):
                continue

            assignee_raw = raw_task.get("assignee")
            assignee_id, matched_name = await resolve_assignee(
                assignee_raw or "",
                employees,
                db,
            )

            deadline = parse_deadline(raw_task.get("deadline"))

            priority_raw = (raw_task.get("priority") or "MEDIUM").upper()
            valid_priorities = {"LOW", "MEDIUM", "HIGH", "URGENT"}
            priority = priority_raw if priority_raw in valid_priorities else "MEDIUM"

            task = Task(
                meeting_id=meeting.id,
                assignee_id=assignee_id,
                assignee_raw=matched_name or assignee_raw,
                title=raw_task["title"][:300],
                description=raw_task.get("description"),
                priority=priority,
                deadline=deadline,
                estimated_hours=raw_task.get("estimated_hours"),
                category=raw_task.get("category", "general"),
                source_quote=raw_task.get("source_quote"),
            )
            db.add(task)
            saved_tasks.append(task)

        await db.flush()
        logger.info(f"Extracted and saved {len(saved_tasks)} tasks for meeting {meeting.id}")
        return saved_tasks


task_extraction_service = TaskExtractionService()
