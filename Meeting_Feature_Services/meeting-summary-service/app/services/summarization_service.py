"""
SummarizationService — completely stateless.
No DB, no Redis, no WebSocket.
Input: transcript text + meeting metadata
Output: structured SummaryResponse
"""
import json
import logging
from app.config import settings
from app.utils.llm_client import chat_complete, safe_parse_json
from app.utils.helpers import chunk_text, deduplicate_list, format_attendees, language_label
from app.prompts.templates import SUMMARIZATION_PROMPT, MERGE_SUMMARIES_PROMPT
from app.schemas.schemas import SummaryResponse, ActionItem

logger = logging.getLogger(__name__)


def _build_empty_summary(meeting_id: int | str, meeting_title: str) -> SummaryResponse:
    return SummaryResponse(
        meeting_id=meeting_id,
        meeting_title=meeting_title,
        summary="No summary available — transcript was empty.",
        key_points=[],
        decisions=[],
        risks=[],
        next_steps=[],
        action_items=[],
        full_markdown=None,
    )


def _parse_action_items(raw_items: list) -> list[ActionItem]:
    result = []
    for item in raw_items:
        if isinstance(item, dict) and item.get("task"):
            result.append(ActionItem(
                task=item["task"],
                owner=item.get("owner") or None,
                deadline=item.get("deadline") or None,
            ))
        elif isinstance(item, str):
            result.append(ActionItem(task=item))
    return result


async def _summarize_chunk(
    chunk: str,
    meeting_title: str,
    attendees_str: str,
    language: str,
) -> dict | None:
    """Run the summarization prompt on a single chunk."""
    prompt = SUMMARIZATION_PROMPT.format(
        transcript=chunk,
        meeting_title=meeting_title,
        attendees=attendees_str,
        language=language_label(language),
    )
    try:
        raw = await chat_complete(
            prompt=prompt,
            system="You are a professional meeting summarizer. Output only valid JSON.",
            expect_json=True,
        )
        return safe_parse_json(raw)
    except Exception as e:
        logger.error(f"Chunk summarization failed: {e}")
        return None


async def _merge_partial_summaries(
    partials: list[dict],
    meeting_title: str,
    attendees_str: str,
) -> dict | None:
    """Merge multiple chunk summaries into one coherent final summary."""
    partials_json = json.dumps(partials, ensure_ascii=False, indent=2)
    prompt = MERGE_SUMMARIES_PROMPT.format(
        partial_summaries=partials_json,
        meeting_title=meeting_title,
        attendees=attendees_str,
    )
    try:
        raw = await chat_complete(
            prompt=prompt,
            system="You are a professional meeting summarizer. Output only valid JSON.",
            expect_json=True,
        )
        return safe_parse_json(raw)
    except Exception as e:
        logger.error(f"Summary merge failed: {e}")
        return None


def _dict_to_response(
    parsed: dict,
    meeting_id: int | str,
    meeting_title: str,
) -> SummaryResponse:
    """Convert a validated LLM output dict to a SummaryResponse."""
    return SummaryResponse(
        meeting_id=meeting_id,
        meeting_title=meeting_title,
        summary=parsed.get("summary", "Summary not available."),
        key_points=deduplicate_list(parsed.get("key_points", [])),
        decisions=deduplicate_list(parsed.get("decisions", [])),
        risks=deduplicate_list(parsed.get("risks", [])),
        next_steps=deduplicate_list(parsed.get("next_steps", [])),
        action_items=_parse_action_items(parsed.get("action_items", [])),
        full_markdown=parsed.get("full_markdown"),
    )


class SummarizationService:

    async def summarize(
        self,
        transcript: str,
        meeting_id: int | str,
        meeting_title: str,
        attendees: list[str],
        language: str = "en",
    ) -> SummaryResponse:
        """
        Generate a structured meeting summary from a transcript.

        For transcripts within the token limit → single LLM call.
        For long transcripts → chunk + summarize each → merge into one final summary.

        Args:
            transcript: Full meeting text
            meeting_id: Identifier echoed in response
            meeting_title: Used in prompts and markdown output
            attendees: Known attendee names
            language: Output language code ('en' | 'ar')

        Returns:
            SummaryResponse with all structured fields populated
        """
        if not transcript.strip():
            logger.warning(f"Empty transcript for meeting {meeting_id}")
            return _build_empty_summary(meeting_id, meeting_title)

        attendees_str = format_attendees(attendees)
        chunks = chunk_text(transcript, max_chars=settings.MAX_TRANSCRIPT_CHARS)
        logger.info(
            f"Summarizing meeting {meeting_id}: {len(transcript)} chars, "
            f"{len(chunks)} chunk(s), language={language}"
        )

        if len(chunks) == 1:
            # Fast path: single chunk, one LLM call
            parsed = await _summarize_chunk(
                chunks[0], meeting_title, attendees_str, language
            )
            if not parsed:
                return _build_empty_summary(meeting_id, meeting_title)
            return _dict_to_response(parsed, meeting_id, meeting_title)

        # Long transcript: summarize each chunk, then merge
        partial_results: list[dict] = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Summarizing chunk {i+1}/{len(chunks)}")
            result = await _summarize_chunk(chunk, meeting_title, attendees_str, language)
            if result:
                partial_results.append(result)

        if not partial_results:
            return _build_empty_summary(meeting_id, meeting_title)

        if len(partial_results) == 1:
            return _dict_to_response(partial_results[0], meeting_id, meeting_title)

        # Merge step
        logger.info(f"Merging {len(partial_results)} partial summaries")
        merged = await _merge_partial_summaries(
            partial_results, meeting_title, attendees_str
        )
        if not merged:
            # Fallback: use first partial if merge fails
            return _dict_to_response(partial_results[0], meeting_id, meeting_title)

        return _dict_to_response(merged, meeting_id, meeting_title)


summarization_service = SummarizationService()
