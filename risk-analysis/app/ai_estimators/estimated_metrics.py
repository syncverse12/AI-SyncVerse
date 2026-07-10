"""
The ONLY module allowed to call the LLM. Enforces the AI Usage Policy:

  "Before estimating any metric using AI, always check whether it can be
  calculated deterministically from available data. The LLM should only
  estimate metrics that cannot be computed directly."

This module also owns the one deliberate exception to "LLM never produces
a numeric score": Budget Risk. Even there, the LLM does NOT output the
score — it outputs a qualitative "Budget Pressure" estimate (High/Medium/
Low) as a metric, and a small deterministic formula in this module (not
the LLM) converts that into the actual Budget Risk RiskCategory score.
That keeps the "no LLM numeric scoring" rule intact.
"""

import json
import logging
from typing import Any, Dict, List, Tuple

from app.ai_context_builder.context_builder import build_context_summary
from app.prompts.estimation_prompts import SYSTEM_PROMPT, build_estimation_prompt
from app.llm.provider_factory import generate_with_fallback
from app.schemas.context_schema import ProjectContext
from app.schemas.report_schema import AIEstimatedMetric, RiskCategory, Recommendation
from app.exceptions.llm import AllLLMProvidersExhaustedError, LLMResponseParsingError

logger = logging.getLogger(__name__)

QUALITATIVE_TO_SCORE = {"low": 20.0, "medium": 50.0, "high": 80.0}


def _severity_from_score(score: float) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def _fallback_result(context: ProjectContext) -> Tuple[List[AIEstimatedMetric], RiskCategory, str, List[Recommendation]]:
    """
    Used when every LLM provider is exhausted. The service must still return
    a usable report — degrade gracefully with explicit low-confidence
    placeholders rather than fail the whole request.
    """
    placeholder_metrics = [
        AIEstimatedMetric(
            name=name, value="Unknown", confidence=0.2,
            reason="All LLM providers were unavailable; no estimate could be generated.",
        )
        for name in ("Team Pressure", "Schedule Stability", "Delivery Confidence", "Budget Pressure")
    ]
    budget_risk = RiskCategory(
        name="Budget Risk", score=50.0, severity="Medium", source="ai_estimated",
        confidence=0.2, reason="LLM unavailable; defaulting to neutral estimate.",
        used_metrics=[],
    )
    narrative = "AI narrative unavailable: all configured LLM providers failed to respond."
    return placeholder_metrics, budget_risk, narrative, []


async def generate_ai_estimated_metrics(
    context: ProjectContext, raw_metrics: Dict[str, Any]
) -> Tuple[List[AIEstimatedMetric], RiskCategory, str, List[Recommendation]]:
    """
    Returns:
      - list of AIEstimatedMetric for the report
      - the Budget Risk RiskCategory (deterministically derived from the
        Budget Pressure estimate, per the docstring above)
      - narrative text
      - list of Recommendation
    """
    context_summary = build_context_summary(context, raw_metrics)
    user_prompt = build_estimation_prompt(context_summary)

    try:
        raw_text, provider_used = await generate_with_fallback(SYSTEM_PROMPT, user_prompt)
    except AllLLMProvidersExhaustedError:
        logger.error("all_llm_providers_exhausted", extra={"event": "all_llm_providers_exhausted"})
        return _fallback_result(context)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error(
            "llm_response_parse_failed",
            extra={"event": "llm_response_parse_failed", "provider": provider_used},
        )
        return _fallback_result(context)

    ai_metrics = [
        AIEstimatedMetric(
            name=m["name"], value=str(m["value"]),
            confidence=float(m.get("confidence", 0.5)), reason=m.get("reason", ""),
        )
        for m in parsed.get("ai_estimated_metrics", [])
    ]

    budget_pressure = next((m for m in ai_metrics if m.name == "Budget Pressure"), None)
    if budget_pressure:
        score = QUALITATIVE_TO_SCORE.get(budget_pressure.value.lower(), 50.0)
        budget_risk = RiskCategory(
            name="Budget Risk", score=score, severity=_severity_from_score(score),
            source="ai_estimated", confidence=budget_pressure.confidence,
            reason=budget_pressure.reason or "Derived from AI-estimated budget pressure.",
            used_metrics=["Effort Consumed (hours)", "Project Budget"],
        )
    else:
        budget_risk = RiskCategory(
            name="Budget Risk", score=50.0, severity="Medium", source="ai_estimated",
            confidence=0.3, reason="No budget pressure estimate returned by the LLM.",
            used_metrics=[],
        )

    narrative = parsed.get("narrative", "")
    recommendations = [
        Recommendation(
            priority=r.get("priority", "Medium"),
            related_risk=r.get("related_risk", "General"),
            action=r.get("action", ""),
        )
        for r in parsed.get("recommendations", [])
    ]

    return ai_metrics, budget_risk, narrative, recommendations
