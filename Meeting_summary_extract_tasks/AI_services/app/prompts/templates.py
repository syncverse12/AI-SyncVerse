TASK_EXTRACTION_PROMPT = """\
You are an expert meeting intelligence AI. Analyze this meeting transcript and extract every actionable task mentioned.

TRANSCRIPT:
{transcript}

KNOWN MEETING ATTENDEES (use these exact names for assignees):
{attendees}

EXTRACTION RULES:
1. Extract EVERY distinct actionable task, assignment, or commitment mentioned
2. For each task, determine the assignee from explicit mentions ("Ahmed will...", "Marwa needs to...") or from context
3. If a task is implicitly assigned (e.g., someone volunteers), still extract it
4. If no specific person is assigned, set assignee to null
5. Priority: URGENT (do today), HIGH (this week), MEDIUM (this sprint), LOW (later)
6. Deadline: extract from phrases like "by Friday", "end of month", "tomorrow" — use YYYY-MM-DD
7. Source quote: the exact sentence(s) from the transcript that indicated this task

Return ONLY valid JSON:
{{
  "tasks": [
    {{
      "title": "short actionable title",
      "description": "additional context if any",
      "assignee": "exact name from attendees list or null",
      "deadline": "YYYY-MM-DD or null",
      "priority": "URGENT|HIGH|MEDIUM|LOW",
      "category": "development|design|testing|meeting|documentation|deployment|general",
      "estimated_hours": 2.0,
      "source_quote": "the exact words from the transcript"
    }}
  ]
}}

IMPORTANT: Return ONLY the JSON. No preamble, no explanation."""


TRANSLATION_PROMPT = """\
You are a professional Arabic-English translator. Translate the following text accurately and naturally.
Preserve speaker labels if present (e.g., "Speaker A:", "Ahmed:").
Preserve all technical terms.
Output ONLY the translation, nothing else.

Translate to {target_language}:
{text}"""


SUMMARIZATION_PROMPT = """\
You are a meeting intelligence AI. Analyze this complete meeting transcript and generate a structured summary.

MEETING TITLE: {title}
ATTENDEES: {attendees}
TRANSCRIPT:
{transcript}

Generate a comprehensive structured summary. Return ONLY valid JSON:
{{
  "overview": "2-3 sentence executive summary of the meeting",
  "key_points": [
    "key discussion point 1",
    "key discussion point 2"
  ],
  "decisions": [
    "decision made during meeting 1",
    "decision made during meeting 2"
  ],
  "blockers": [
    "blocker or risk mentioned 1"
  ],
  "next_steps": [
    "next step or follow-up 1"
  ],
  "action_items": [
    {{
      "task": "task description",
      "owner": "person name or 'Team'",
      "deadline": "YYYY-MM-DD or null"
    }}
  ],
  "full_markdown": "# Meeting Summary\\n\\n## Overview\\n...full markdown summary..."
}}

IMPORTANT: Return ONLY the JSON object."""


ASSIGNEE_RESOLUTION_PROMPT = """\
Given this list of known employees and this extracted task assignee name, find the best match.

KNOWN EMPLOYEES:
{employees}

EXTRACTED ASSIGNEE NAME: "{raw_name}"

Rules:
- Match by first name, last name, or full name (case-insensitive)
- If "Ahmed M." appears, match "Ahmed Mohamed" if present
- If no confident match exists, return null
- If multiple matches, return the most likely one based on context

Return ONLY valid JSON:
{{
  "matched_id": "employee_uuid or null",
  "matched_name": "exact matched name or null",
  "confidence": 0.0
}}"""
