TASK_EXTRACTION_PROMPT = """\
You are an expert meeting intelligence AI specialized in extracting actionable tasks.

MEETING TRANSCRIPT:
{transcript}

KNOWN ATTENDEES (use these exact names when assigning tasks):
{attendees}

MEETING DATE (for resolving relative deadlines like "by Friday"):
{meeting_date}

━━━ EXTRACTION RULES ━━━

1. TASKS: Extract every distinct commitment, assignment, or action item mentioned.
   - Direct: "Ahmed will deploy the backend"
   - Indirect: "Someone needs to update the docs" (assignee may be null)
   - Implicit: "I'll handle that" (speaker is assignee if identifiable)

2. ASSIGNEE:
   - Match against the KNOWN ATTENDEES list (case-insensitive, first name OK)
   - If the person is not in the list but clearly named, use their name as-is
   - If unknown or ambiguous → null

3. DEADLINE:
   - Convert relative dates using MEETING DATE as reference
   - "tomorrow" → MEETING_DATE + 1 day → format YYYY-MM-DD
   - "by Friday" → next Friday from MEETING DATE → YYYY-MM-DD
   - "end of sprint" / "next week" → best estimate or null
   - If no deadline mentioned → null

4. PRIORITY:
   - URGENT: "immediately", "ASAP", "right now", "today", "blocking"
   - HIGH: "this week", "important", "soon", "priority"
   - MEDIUM: default when no qualifier given
   - LOW: "when you get a chance", "eventually", "backlog"

5. CATEGORY: development | design | testing | meeting | documentation | deployment | research | general

6. CONFIDENCE: Your confidence that this is a real assigned task (0.0–1.0)
   - Named person + verb + clear task → 0.95
   - Implied assignment → 0.70–0.85
   - Very vague → 0.50–0.65

7. SOURCE QUOTE: The exact sentence(s) from the transcript that evidence this task.

━━━ OUTPUT FORMAT ━━━

Return ONLY valid JSON with no preamble:
{{
  "tasks": [
    {{
      "title": "Short imperative task title",
      "description": "Additional context not captured in title/other fields, or null",
      "assignee": "Person name from attendees list or null",
      "deadline": "YYYY-MM-DD or null",
      "priority": "URGENT|HIGH|MEDIUM|LOW",
      "category": "category string",
      "estimated_hours": 2.0,
      "source_quote": "exact words from transcript",
      "confidence": 0.92
    }}
  ]
}}"""


ASSIGNEE_RESOLUTION_PROMPT = """\
Match this extracted name to the closest person in the employee list.

EMPLOYEE LIST:
{employees}

EXTRACTED NAME: "{raw_name}"

RULES:
- Match by first name, last name, or full name (case-insensitive)
- Partial matches are OK ("Ahmed M." → "Ahmed Mohamed")
- If confidence < 0.7, return matched_id as null
- Return only one match (the most likely)

Return ONLY valid JSON:
{{
  "matched_id": "id string or null",
  "matched_name": "exact matched name or null",
  "confidence": 0.0
}}"""
