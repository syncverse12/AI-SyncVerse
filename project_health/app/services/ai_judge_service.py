"""
app/services/ai_judge_service.py
Layer 3b – AI Judge: RAG-grounded LLM evaluation with optional critic loop.
"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.domain import AIJudgeResult, Project, RiskLevel
from app.services.rag_service import RAGContext

logger = get_logger(__name__)


# ─── Prompt templates ────────────────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """You are a senior AI project evaluator acting as:
- Senior Project Manager
- QA Engineer
- Client Representative
- Risk Analyst

Your evaluation must be EVIDENCE-BASED using only the provided context retrieved from the vector database.
You must detect hidden failures even when numeric metrics look acceptable.
Be precise, critical, and actionable.

ALWAYS respond with valid JSON only. No markdown, no preamble.
"""

JUDGE_USER_TEMPLATE = """
=== PROJECT EVALUATION REQUEST ===

PROJECT: {project_name}
DESCRIPTION: {project_description}

=== RETRIEVED CONTEXT (from Qdrant RAG) ===

[REQUIREMENTS]:
{requirements}

[TASKS]:
{tasks}

[DELIVERABLES]:
{deliverables}

=== METRICS ===

Health Score: {health_score}/100
Client Alignment Score: {alignment_score}/100

Delayed Tasks:
{delayed_tasks}

Goal Progress:
{goal_progress}

Low-Alignment Requirements (critical):
{low_alignment_requirements}

=== EVALUATION INSTRUCTIONS ===

Evaluate across these 5 dimensions:
1. Requirement Coverage — are ALL requirements genuinely satisfied?
2. Semantic Completeness — does the work satisfy intent, not just keywords?
3. Execution Quality — is implementation correct, complete, and usable?
4. Risk Detection — bottlenecks, delays, overloaded resources, unstable progress
5. Consistency Check — alignment between requirements ↔ tasks ↔ goals ↔ deliverables

IMPORTANT:
- Detect HIDDEN failures (tasks completed but irrelevant / misleading)
- Identify missing requirement coverage (gaps not caught by metric scores)
- Penalise orphan work, scope creep, or low-quality completions
- If health_score looks high but alignment is low → flag as misleading metric

=== REQUIRED JSON OUTPUT ===
{{
  "ai_judge_score": <integer 0-100>,
  "confidence": <float 0.0-1.0>,
  "adjusted_health_score": <integer 0-100>,
  "risk_level": "low" | "medium" | "high" | "critical",
  "summary": "<2-4 sentence human-readable reasoning>",
  "key_issues": ["<issue1>", "<issue2>", ...],
  "recommendations": ["<rec1>", "<rec2>", ...],
  "detected_gaps": ["<gap1>", "<gap2>", ...]
}}
"""

CRITIC_SYSTEM_PROMPT = """You are a second-opinion AI critic reviewing another AI's project evaluation.
Your job: validate whether the judgment is fair, evidence-based, and consistent.
Point out if the first evaluator was too harsh, too lenient, missed key issues, or hallucinated problems.
Respond with valid JSON only.
"""

CRITIC_USER_TEMPLATE = """
Original evaluation:
{original_judgment}

Project context summary:
- Health Score: {health_score}
- Alignment Score: {alignment_score}
- Delayed tasks: {delayed_count}

Validate and optionally correct the evaluation. Respond with:
{{
  "validated": true | false,
  "adjusted_ai_judge_score": <integer 0-100 or null if no change>,
  "critic_notes": "<brief critique or confirmation>",
  "confidence_adjustment": <float -0.2 to 0.2>
}}
"""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _fmt_list(items: list[Any], limit: int = 6) -> str:
    if not items:
        return "None"
    subset = items[:limit]
    lines = [f"  - {json.dumps(item, default=str)}" for item in subset]
    if len(items) > limit:
        lines.append(f"  ... and {len(items) - limit} more")
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    return json.loads(text)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def _call_llm(
    system: str,
    user: str,
    model: str,
    max_tokens: int = 1024,
) -> str:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or "{}"


# ─── Main judge ──────────────────────────────────────────────────────────────

async def run_ai_judge(
    project: Project,
    ctx: RAGContext,
    run_critic: bool = True,
) -> AIJudgeResult:
    """
    Call the primary LLM judge (grounded on RAG context),
    then optionally run a critic LLM to validate the result.
    """
    settings = get_settings()

    user_prompt = JUDGE_USER_TEMPLATE.format(
        project_name=project.name,
        project_description=project.description,
        requirements=_fmt_list(ctx.retrieved_requirements),
        tasks=_fmt_list(ctx.retrieved_tasks),
        deliverables=_fmt_list(ctx.retrieved_deliverables),
        health_score=ctx.health_score,
        alignment_score=ctx.alignment_score,
        delayed_tasks=_fmt_list(ctx.delayed_tasks_summary),
        goal_progress=_fmt_list(ctx.goal_progress_summary),
        low_alignment_requirements=_fmt_list(ctx.low_alignment_requirements),
    )

    logger.info("ai_judge_calling_llm", project_id=project.id)
    raw_response = await _call_llm(
        system=JUDGE_SYSTEM_PROMPT,
        user=user_prompt,
        model=settings.openai_llm_model,
        max_tokens=1500,
    )

    try:
        judgment = _extract_json(raw_response)
    except Exception as exc:
        logger.error("ai_judge_parse_error", error=str(exc), raw=raw_response[:300])
        judgment = {
            "ai_judge_score": 0,
            "confidence": 0.0,
            "adjusted_health_score": int(ctx.health_score),
            "risk_level": "high",
            "summary": "Evaluation failed due to LLM parse error.",
            "key_issues": ["LLM response could not be parsed"],
            "recommendations": ["Retry evaluation"],
            "detected_gaps": [],
        }

    # ── Critic loop ───────────────────────────────────────────────────────────
    critic_validated = False
    critic_notes: str | None = None

    if run_critic:
        critic_prompt = CRITIC_USER_TEMPLATE.format(
            original_judgment=json.dumps(judgment, indent=2),
            health_score=ctx.health_score,
            alignment_score=ctx.alignment_score,
            delayed_count=len(ctx.delayed_tasks_summary),
        )
        logger.info("ai_judge_critic_loop", project_id=project.id)
        try:
            critic_raw = await _call_llm(
                system=CRITIC_SYSTEM_PROMPT,
                user=critic_prompt,
                model=settings.openai_llm_model,
                max_tokens=600,
            )
            critic_result = _extract_json(critic_raw)
            critic_validated = critic_result.get("validated", False)
            critic_notes = critic_result.get("critic_notes")

            # Apply critic score correction if provided
            corrected_score = critic_result.get("adjusted_ai_judge_score")
            if corrected_score is not None:
                judgment["ai_judge_score"] = corrected_score

            # Apply confidence adjustment
            adj = critic_result.get("confidence_adjustment", 0.0)
            judgment["confidence"] = max(0.0, min(1.0, judgment.get("confidence", 0.5) + adj))

        except Exception as exc:
            logger.warning("critic_loop_failed", error=str(exc))

    # ── Build result ──────────────────────────────────────────────────────────
    risk_raw = judgment.get("risk_level", "medium").lower()
    try:
        risk = RiskLevel(risk_raw)
    except ValueError:
        risk = RiskLevel.MEDIUM

    result = AIJudgeResult(
        project_id=project.id,
        ai_judge_score=float(judgment.get("ai_judge_score", 0)),
        confidence=float(judgment.get("confidence", 0.5)),
        adjusted_health_score=float(judgment.get("adjusted_health_score", ctx.health_score)),
        risk_level=risk,
        summary=judgment.get("summary", ""),
        key_issues=judgment.get("key_issues", []),
        recommendations=judgment.get("recommendations", []),
        detected_gaps=judgment.get("detected_gaps", []),
        critic_validated=critic_validated,
        critic_notes=critic_notes,
    )

    logger.info(
        "ai_judge_complete",
        project_id=project.id,
        score=result.ai_judge_score,
        risk=result.risk_level,
        critic_validated=critic_validated,
    )
    return result
