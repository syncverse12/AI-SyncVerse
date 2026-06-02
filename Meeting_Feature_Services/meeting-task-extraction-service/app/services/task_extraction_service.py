"""
TaskExtractionService — completely stateless.
No DB, no Redis, no WebSocket.
Input: transcript text + optional attendee list
Output: list of structured ExtractedTask objects
"""
import logging
from typing import Optional
from app.config import settings
from app.utils.llm_client import chat_complete, safe_parse_json
from app.utils.helpers import (
    chunk_text, names_match, parse_flexible_date,
    extract_person_names_regex, today_str,
)
from app.prompts.templates import TASK_EXTRACTION_PROMPT
from app.schemas.schemas import ExtractedTask

logger = logging.getLogger(__name__)

# Try to load spaCy NER — graceful fallback if not installed
_nlp = None
if settings.USE_SPACY_NER:
    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
        logger.info("spaCy NER loaded successfully")
    except Exception as e:
        logger.warning(f"spaCy not available, using regex fallback: {e}")


def _ner_person_names(text: str) -> list[str]:
    """Extract PERSON entity names using spaCy or regex fallback."""
    if _nlp:
        doc = _nlp(text[:50_000])
        return list({ent.text for ent in doc.ents if ent.label_ == "PERSON"})
    return extract_person_names_regex(text)


def _build_attendees_string(attendees: list[str], ner_names: list[str]) -> str:
    """Merge caller-supplied attendees with NER-found names, deduplicated."""
    combined = list(dict.fromkeys(attendees + ner_names))
    if not combined:
        return "(no named attendees provided)"
    return "\n".join(f"- {name}" for name in combined)


def _validate_task_dict(raw: dict) -> Optional[ExtractedTask]:
    """Validate and coerce a raw dict from LLM into an ExtractedTask."""
    if not raw.get("title"):
        return None
    deadline = parse_flexible_date(raw.get("deadline"))
    try:
        return ExtractedTask(
            title=str(raw["title"])[:300],
            description=raw.get("description") or None,
            assignee=raw.get("assignee") or None,
            deadline=deadline,
            priority=raw.get("priority", "MEDIUM"),
            category=raw.get("category", "general"),
            estimated_hours=raw.get("estimated_hours"),
            source_quote=raw.get("source_quote") or None,
            confidence=float(raw.get("confidence", 0.9)),
        )
    except Exception as e:
        logger.warning(f"Task validation failed for '{raw.get('title')}': {e}")
        return None


async def _extract_from_chunk(
    chunk: str,
    attendees_str: str,
    meeting_date: str,
) -> list[dict]:
    """Run the LLM extraction prompt on a single text chunk."""
    prompt = TASK_EXTRACTION_PROMPT.format(
        transcript=chunk,
        attendees=attendees_str,
        meeting_date=meeting_date,
    )
    raw = await chat_complete(
        prompt=prompt,
        system="You are a meeting task extraction AI. Output only valid JSON.",
        temperature=settings.GROQ_TEMPERATURE,
        expect_json=True,
    )
    parsed = safe_parse_json(raw)
    if not parsed or "tasks" not in parsed:
        logger.warning("LLM returned no parseable tasks")
        return []
    return parsed["tasks"]


def _deduplicate_tasks(tasks: list[ExtractedTask]) -> list[ExtractedTask]:
    """
    Remove duplicate tasks across chunks.
    Two tasks are duplicates if their titles are very similar (>80% word overlap).
    """
    seen_titles: list[str] = []
    unique: list[ExtractedTask] = []
    for task in tasks:
        title_words = set(task.title.lower().split())
        is_dup = False
        for seen in seen_titles:
            seen_words = set(seen.split())
            overlap = len(title_words & seen_words) / max(len(title_words | seen_words), 1)
            if overlap >= 0.8:
                is_dup = True
                break
        if not is_dup:
            seen_titles.append(task.title.lower())
            unique.append(task)
    return unique


class TaskExtractionService:

    async def extract(
        self,
        transcript: str,
        attendees: list[str],
        meeting_date: Optional[str] = None,
    ) -> tuple[list[ExtractedTask], list[str]]:
        """
        Main extraction entry point.

        Args:
            transcript: Full meeting text (any language, translated to EN before calling)
            attendees: List of known attendee names
            meeting_date: YYYY-MM-DD string for deadline resolution

        Returns:
            (list of ExtractedTask, list of processing notes)
        """
        notes: list[str] = []

        if not transcript.strip():
            return [], ["Transcript was empty — no tasks extracted."]

        effective_date = meeting_date or today_str()

        # Step 1: NER scan to supplement the attendee list
        ner_names = _ner_person_names(transcript)
        if ner_names:
            notes.append(f"NER found {len(ner_names)} person name(s) in transcript.")
        attendees_str = _build_attendees_string(attendees, ner_names)

        # Step 2: Chunk transcript if too long
        chunks = chunk_text(transcript, max_chars=8000)
        if len(chunks) > 1:
            notes.append(f"Transcript split into {len(chunks)} chunks for processing.")

        # Step 3: Extract tasks from each chunk
        all_raw: list[dict] = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Extracting tasks from chunk {i+1}/{len(chunks)}")
            raw_tasks = await _extract_from_chunk(chunk, attendees_str, effective_date)
            all_raw.extend(raw_tasks)

        # Step 4: Validate each raw task dict into ExtractedTask
        validated: list[ExtractedTask] = []
        for raw in all_raw:
            task = _validate_task_dict(raw)
            if task:
                validated.append(task)
            else:
                notes.append(f"Skipped malformed task: {raw.get('title', '?')!r}")

        # Step 5: Deduplicate across chunks
        deduped = _deduplicate_tasks(validated)
        if len(deduped) < len(validated):
            notes.append(f"Removed {len(validated) - len(deduped)} duplicate task(s).")

        logger.info(f"Extraction complete: {len(deduped)} tasks from {len(transcript)} chars")
        return deduped, notes


task_extraction_service = TaskExtractionService()
