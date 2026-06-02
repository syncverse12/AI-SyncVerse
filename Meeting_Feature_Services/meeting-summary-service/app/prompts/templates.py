SUMMARIZATION_PROMPT = """\
You are an expert meeting intelligence AI. Generate a comprehensive structured summary of this meeting.

MEETING TITLE: {meeting_title}
ATTENDEES: {attendees}
OUTPUT LANGUAGE: {language}

TRANSCRIPT:
{transcript}

━━━ INSTRUCTIONS ━━━

Analyze the transcript carefully and produce:

1. SUMMARY: A concise 2-4 sentence executive overview capturing the essence of the meeting.

2. KEY POINTS: The 3-7 most important topics discussed.
   - Each point is one clear sentence
   - Focus on what was discussed, not who said it

3. DECISIONS: Concrete decisions that were made or agreed upon.
   - Only include firm decisions, not suggestions or maybes
   - E.g. "Decided to migrate to PostgreSQL"

4. RISKS: Blockers, concerns, or risks mentioned during the meeting.
   - Include both technical and business risks
   - Include unresolved questions that could block progress

5. NEXT STEPS: Follow-up actions the team needs to take.
   - Higher-level than individual tasks
   - E.g. "Schedule follow-up review after deployment"

6. ACTION ITEMS: Specific assigned tasks with owner and deadline.
   - Only include items with a clear owner
   - Deadline: YYYY-MM-DD format or null

7. FULL MARKDOWN: A complete, well-formatted markdown document of the summary.
   Use proper headers, bullet points, and bold text.

━━━ OUTPUT FORMAT ━━━

Return ONLY valid JSON with no preamble or explanation:
{{
  "summary": "2-4 sentence executive overview",
  "key_points": [
    "Key discussion point 1",
    "Key discussion point 2"
  ],
  "decisions": [
    "Decision 1 made during the meeting"
  ],
  "risks": [
    "Risk or blocker identified"
  ],
  "next_steps": [
    "Next step 1"
  ],
  "action_items": [
    {{
      "task": "Task description",
      "owner": "Person name or null",
      "deadline": "YYYY-MM-DD or null"
    }}
  ],
  "full_markdown": "# {meeting_title}\\n\\n## Summary\\n..."
}}"""


MERGE_SUMMARIES_PROMPT = """\
You are given multiple partial summaries of sections of the same meeting.
Merge them into one coherent, deduplicated summary.

PARTIAL SUMMARIES:
{partial_summaries}

MEETING TITLE: {meeting_title}
ATTENDEES: {attendees}

Rules:
- Deduplicate overlapping points
- Keep all unique decisions and risks
- Merge action items without duplicates
- Write the final summary as if summarizing the whole meeting at once

Return ONLY valid JSON using exactly this schema:
{{
  "summary": "...",
  "key_points": [],
  "decisions": [],
  "risks": [],
  "next_steps": [],
  "action_items": [{{"task": "...", "owner": "...", "deadline": "..."}}],
  "full_markdown": "..."
}}"""
