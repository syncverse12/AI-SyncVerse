"""
The Orchestrator. Coordinates the full pipeline in strict order and owns
NO calculation logic itself — every number comes from a dedicated layer.

    Data Collector -> Metrics Engine -> Risk Engine -> AI Context Builder
    -> LLM (via ai_estimators) -> Report Builder

Any layer's specific failure mode is caught here and translated into a
degraded-but-valid report rather than a 500, except for total data
unavailability (ProjectNotFoundError), which propagates to the router as
a 404.
"""

import logging
import time
import httpx

from app.data_collector.collector_factory import get_project_context
from app.metrics.metrics_engine import compute_all_metrics
from app.risk_engine.rules import (
    calculate_timeline_risk, calculate_resource_risk, calculate_productivity_risk,
    calculate_dependency_risk, calculate_communication_risk, calculate_confirmed_risk_component,
)
from app.risk_engine.aggregator import aggregate_overall_risk
from app.ai_estimators.estimated_metrics import generate_ai_estimated_metrics
from app.report_builder.report_builder import build_report
from app.persistence.sqlite_adapter import SQLitePersistenceAdapter
from app.schemas.report_schema import RiskReport
from app.core.logging_config import log_duration

logger = logging.getLogger(__name__)
_persistence = SQLitePersistenceAdapter()


async def generate_risk_report(project_id: str, http_client: httpx.AsyncClient) -> RiskReport:
    start = time.perf_counter()

    # 1. Data Collector
    context = await get_project_context(project_id, http_client)

    # 2. Metrics Engine (deterministic)
    metrics_result = compute_all_metrics(context)
    raw = metrics_result["raw"]
    calculated_metrics = metrics_result["display_metrics"]

    # 3. Risk Engine (deterministic, rule-based — no LLM)
    risk_categories = [
        calculate_timeline_risk(raw),
        calculate_resource_risk(raw),
        calculate_productivity_risk(raw),
        calculate_dependency_risk(raw, total_tasks=len(context.tasks)),
        calculate_communication_risk(raw, project_priority=context.project.priority),
        calculate_confirmed_risk_component(raw),
    ]

    # 4 & 5. AI Context Builder + LLM (via ai_estimators — the only module
    # allowed to call an LLM provider). Produces Budget Risk (the one
    # category with no deterministic data source) plus qualitative metrics,
    # narrative, and recommendations.
    with log_duration(logger, "ai_estimation_phase", project_id=project_id):
        ai_metrics, budget_risk, narrative, recommendations = await generate_ai_estimated_metrics(
            context, raw
        )
    risk_categories.append(budget_risk)

    # Aggregate overall score from all categories (rule-based, config-driven weights)
    overall_risk = aggregate_overall_risk(risk_categories)

    # 6. Report Builder — the only place the final JSON is assembled
    execution_time_ms = round((time.perf_counter() - start) * 1000, 1)
    model_used = "unavailable" if not ai_metrics or all(m.value == "Unknown" for m in ai_metrics) else "llm-provider-chain"

    report = build_report(
        context=context,
        overall_risk=overall_risk,
        risk_categories=risk_categories,
        calculated_metrics=calculated_metrics,
        ai_estimated_metrics=ai_metrics,
        recommendations=recommendations,
        execution_time_ms=execution_time_ms,
        model_used=model_used,
    )

    # Persist for history endpoint + future trend metrics
    await _persistence.save_report(report)
    await _persistence.save_snapshot(project_id, {
        "progress_pct": raw.get("progress_pct"),
        "total_tasks": len(context.tasks),
        "overall_risk_score": overall_risk.score,
    })

    logger.info(
        "risk_report_generated",
        extra={"event": "risk_report_generated", "project_id": project_id, "duration_ms": execution_time_ms},
    )
    return report


async def get_report_history(project_id: str, limit: int = 20):
    return await _persistence.get_report_history(project_id, limit=limit)
