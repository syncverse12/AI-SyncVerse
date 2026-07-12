"""
ai/enrichment.py
-----------------
        Metrics Engine
                |
        AI Enrichment      <-- you are here
                |
        Workload Engine

Produces exactly the metrics that cannot be derived mathematically
(§3/§4 of docs/DATABASE_ANALYSIS.md), for every employee in the context,
in ONE LLM request — never one call per employee, never one call per metric.

Fully optional: if no provider is configured or every provider fails, the
context keeps the deterministic heuristic values the Context Builder
already seeded, and a data_quality_warning is recorded instead of raising.
"""

from __future__ import annotations
import json
from typing import Dict

from app.ai.factory import complete_with_fallback
from app.core.exceptions import LLMProviderError, ProviderNotConfiguredError
from app.core.logging import get_logger, timed
from app.models.ai_models import AIEstimatedValue, EmployeeAIEnrichment
from app.models.context import WorkloadContext
from app.models.schemas import ComplexityLevel, TaskComplexityDistribution

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are a workload analysis assistant for a software engineering team.
You will receive employees and their active tasks. For EACH employee, estimate the
metrics listed below. Base every estimate on the task titles/descriptions/priorities and
deterministic signals given — never invent facts not present in the input.

Return ONLY a JSON object of this exact shape (no prose, no markdown fences):
{
  "employees": {
    "<employee_id>": {
      "task_complexity_counts": {"low": int, "medium": int, "high": int, "critical": int},
      "estimated_task_difficulty": {"value": str, "confidence": float, "reason": str},
      "estimated_work_complexity": {"value": str, "confidence": float, "reason": str},
      "burnout_indicator": {"value": "low"|"moderate"|"high", "confidence": float, "reason": str},
      "productivity_trend": {"value": "improving"|"stable"|"declining", "confidence": float, "reason": str},
      "focus_capacity": {"value": str, "confidence": float, "reason": str},
      "context_switching_cost": {"value": "low"|"medium"|"high", "confidence": float, "reason": str},
      "collaboration_difficulty": {"value": "low"|"medium"|"high", "confidence": float, "reason": str},
      "estimated_priority_weight": {"value": float, "confidence": float, "reason": str},
      "availability_score": {"value": float, "confidence": float, "reason": str},
      "narrative": str
    }
  }
}
task_complexity_counts must sum to that employee's active task count.
availability_score and estimated_priority_weight are 0-100 floats. confidence is 0-1.
"""


class AIEnrichmentLayer:
    async def enrich(self, context: WorkloadContext) -> WorkloadContext:
        if not context.employees:
            return context

        user_prompt = self._build_user_prompt(context)

        try:
            with timed(logger, "ai_enrichment_batch", employee_count=len(context.employees)):
                raw_text, provider_used = await complete_with_fallback(_SYSTEM_PROMPT, user_prompt)
            parsed = self._parse(raw_text)
            self._apply(context, parsed, provider_used)
        except ProviderNotConfiguredError as exc:
            logger.info("AI enrichment skipped — no provider configured", extra={"reason": str(exc)})
            context.data_quality_warnings.append(
                "AI enrichment skipped (no LLM provider configured) — using deterministic heuristics only."
            )
        except LLMProviderError as exc:
            logger.error("AI enrichment failed after fallback chain", extra={"error": str(exc)})
            context.data_quality_warnings.append(
                f"AI enrichment failed ({exc}) — using deterministic heuristics only."
            )
        except Exception as exc:  # noqa: BLE001 — never let enrichment crash the pipeline
            logger.error("AI enrichment unexpected error", extra={"error": str(exc)})
            context.data_quality_warnings.append(
                "AI enrichment returned an unusable response — using deterministic heuristics only."
            )

        return context

    # ------------------------------------------------------------------

    def _build_user_prompt(self, context: WorkloadContext) -> str:
        employees_payload = []
        by_ext_id = {emp.name: emp for emp in context.employees}  # for internal lookup only
        for ext_id, raw_tasks in context.raw_tasks_by_employee.items():
            active = [t for t in raw_tasks if t.is_active]
            employees_payload.append({
                "employee_id": ext_id,
                "active_task_count": len(active),
                "tasks": [
                    {"title": t.title, "description": (t.description or "")[:300],
                     "priority": t.priority, "category": t.category_name, "is_overdue": t.is_overdue}
                    for t in active[:15]  # cap payload size per employee
                ],
            })
        return json.dumps({"employees": employees_payload}, default=str)

    def _parse(self, raw_text: str) -> dict:
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[-1] if "\n" in text else text
        return json.loads(text)

    def _apply(self, context: WorkloadContext, parsed: dict, provider_used: str) -> None:
        employees_data: Dict[str, dict] = parsed.get("employees", {})
        # Map external raw ids -> internal Employee objects via raw_tasks_by_employee's key order
        ext_ids = list(context.raw_tasks_by_employee.keys())
        for ext_id, employee in zip(ext_ids, context.employees):
            data = employees_data.get(ext_id)
            if not data:
                continue
            try:
                counts = data.get("task_complexity_counts", {})
                employee.task_complexity_distribution = TaskComplexityDistribution(
                    low=int(counts.get("low", 0)), medium=int(counts.get("medium", 0)),
                    high=int(counts.get("high", 0)), critical=int(counts.get("critical", 0)),
                )
                if "availability_score" in data:
                    employee.availability_score = float(
                        max(0.0, min(100.0, data["availability_score"].get("value", employee.availability_score)))
                    )
                enrichment = EmployeeAIEnrichment(
                    estimated_task_difficulty=AIEstimatedValue(**data["estimated_task_difficulty"]),
                    estimated_work_complexity=AIEstimatedValue(**data["estimated_work_complexity"]),
                    burnout_indicator=AIEstimatedValue(**data["burnout_indicator"]),
                    productivity_trend=AIEstimatedValue(**data["productivity_trend"]),
                    focus_capacity=AIEstimatedValue(**data["focus_capacity"]),
                    context_switching_cost=AIEstimatedValue(**data["context_switching_cost"]),
                    collaboration_difficulty=AIEstimatedValue(**data["collaboration_difficulty"]),
                    estimated_priority_weight=AIEstimatedValue(**data["estimated_priority_weight"]),
                    availability_score=AIEstimatedValue(**data["availability_score"]),
                    narrative=data.get("narrative", ""),
                )
                employee.ai_enrichment = enrichment.model_dump()
                employee.ai_enrichment["provider_used"] = provider_used
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning(
                    "Skipping malformed AI enrichment for one employee",
                    extra={"employee": employee.name, "error": str(exc)},
                )
                continue
