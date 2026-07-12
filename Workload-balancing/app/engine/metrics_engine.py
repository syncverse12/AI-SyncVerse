"""
engine/metrics_engine.py
--------------------------
        Context Builder
                |
        Metrics Engine     <-- you are here
                |
        AI Enrichment

Pure Python, no LLM calls. Computes team-level deterministic aggregates
that sit alongside (not instead of) the per-employee WorkloadMetrics that
the preserved WorkloadMonitor produces later in the Workload Engine step.
"""

from __future__ import annotations
import statistics
from typing import Any, Dict

from app.models.context import WorkloadContext


class MetricsEngine:
    def compute(self, context: WorkloadContext) -> Dict[str, Any]:
        employees = context.employees
        tasks = context.tasks

        if not employees:
            return {"employee_count": 0}

        active_totals = [e.active_tasks for e in employees]
        delayed_totals = [e.delayed_tasks for e in employees]
        availability = [e.availability_score for e in employees]
        success_rates = [e.past_success_rate for e in employees]

        capacity_utilization = round(
            statistics.fmean([100 - a for a in availability]) if availability else 0.0, 1
        )
        overdue_tasks = [t for t in tasks if t.is_delayed]

        return {
            "employee_count": len(employees),
            "task_count": len(tasks),
            "total_active_tasks": sum(active_totals),
            "total_delayed_tasks": sum(delayed_totals),
            "team_capacity_utilization_pct": capacity_utilization,
            "team_avg_availability": round(statistics.fmean(availability), 1) if availability else 0.0,
            "team_task_distribution_variance": round(statistics.pvariance(active_totals), 2)
            if len(active_totals) > 1 else 0.0,
            "team_avg_success_rate": round(statistics.fmean(success_rates), 2) if success_rates else 0.0,
            "overdue_task_ratio": round(len(overdue_tasks) / len(tasks), 2) if tasks else 0.0,
        }
