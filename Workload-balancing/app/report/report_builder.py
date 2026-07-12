"""
report/report_builder.py
--------------------------
        Workload Engine
                |
        Report Builder     <-- you are here

The ONLY place that assembles the final API response shape. The LLM never
touches this layer directly — by this point AI output already lives on
each Employee's `ai_enrichment` field (attached by ai/enrichment.py).
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.exceptions import ReportGenerationError
from app.engine.workload_engine import WorkloadEngineResult
from app.models.context import WorkloadContext
from app.models.schemas import BalanceReport


class ReportBuilder:
    def build(
        self,
        context: WorkloadContext,
        engine_result: WorkloadEngineResult,
        deterministic_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            report = BalanceReport(
                status=engine_result.risk_report.status,
                timestamp=_now(),
                team_health_score=engine_result.risk_report.team_health_score,
                overloaded_employees=engine_result.risk_report.overloaded,
                underutilized_employees=engine_result.risk_report.underutilized,
                bottleneck_employees=engine_result.risk_report.bottlenecks,
                recommended_actions=engine_result.actions,
                summary=engine_result.risk_report.summary,
                metrics={
                    **deterministic_metrics,
                    "overloaded_count": len(engine_result.risk_report.overloaded),
                    "underutilized_count": len(engine_result.risk_report.underutilized),
                    "bottleneck_count": len(engine_result.risk_report.bottlenecks),
                    "score_variance": engine_result.risk_report.score_variance,
                    "action_count": len(engine_result.actions),
                },
            )
        except Exception as exc:  # noqa: BLE001
            raise ReportGenerationError(f"Failed to assemble report: {exc}") from exc

        ai_narratives = [
            {"employee": e.name, "narrative": e.ai_enrichment.get("narrative")}
            for e in context.employees
            if e.ai_enrichment and e.ai_enrichment.get("narrative")
        ]

        return {
            "scope_type": context.scope_type,
            "scope_id": context.scope_id,
            "scope_name": context.scope_name,
            "source": context.source,
            "report": report.model_dump(),
            "employee_ai_enrichment": {
                e.name: e.ai_enrichment for e in context.employees if e.ai_enrichment
            },
            "ai_narratives": ai_narratives,
            "data_quality_warnings": context.data_quality_warnings,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
