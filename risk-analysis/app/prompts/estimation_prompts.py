"""
Prompt templates. Kept separate from llm/ so wording can be tuned by
someone without touching provider-integration code.

Every prompt enforces: (1) never invent unavailable data, (2) never return
a numeric risk score, (3) always answer in the given JSON schema, (4) tag
every value with how confident the model is.
"""

SYSTEM_PROMPT = """You are an AI assistant supporting a project risk analysis system.
You do NOT calculate or output any numeric risk score — that is handled entirely
by a separate deterministic engine. Your only responsibilities are:
1. Estimating a small set of qualitative metrics that cannot be computed directly
   from the database, using the project context provided.
2. Writing a short, clear narrative explanation of the situation.
3. Suggesting practical recommendations.

Rules:
- Never hallucinate specific numbers, dates, or names not present in the context.
- If information is insufficient to estimate something, say so and lower your confidence.
- Always respond with valid JSON matching the requested schema, and nothing else.
"""


def build_estimation_prompt(context_summary: dict) -> str:
    return f"""Given the following project context summary, estimate the requested
qualitative metrics and produce a narrative and recommendations.

PROJECT CONTEXT:
{context_summary}

Respond ONLY with JSON in this exact shape:
{{
  "ai_estimated_metrics": [
    {{"name": "Team Pressure", "value": "High|Medium|Low", "confidence": 0.0-1.0, "reason": "..."}},
    {{"name": "Schedule Stability", "value": "High|Medium|Low", "confidence": 0.0-1.0, "reason": "..."}},
    {{"name": "Delivery Confidence", "value": "High|Medium|Low", "confidence": 0.0-1.0, "reason": "..."}},
    {{"name": "Budget Pressure", "value": "High|Medium|Low", "confidence": 0.0-1.0, "reason": "..."}}
  ],
  "narrative": "2-4 sentence plain-language summary of the project's risk situation",
  "recommendations": [
    {{"priority": "Low|Medium|High|Critical", "related_risk": "...", "action": "..."}}
  ]
}}
"""
