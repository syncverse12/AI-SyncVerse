"""
Aggregates every category-specific metric module into one bundle.

This is the single entry point the Orchestrator calls after the Data
Collector returns a ProjectContext. Nothing in this file calls the LLM —
that rule is enforced simply by never importing app.llm here.
"""

from typing import Any, Dict, List
from app.schemas.context_schema import ProjectContext
from app.schemas.report_schema import CalculatedMetric
from app.metrics.timeline_metrics import compute_timeline_metrics
from app.metrics.workload_metrics import compute_workload_metrics
from app.metrics.productivity_metrics import compute_productivity_metrics
from app.metrics.dependency_metrics import compute_dependency_and_confirmed_risk_metrics


def compute_all_metrics(context: ProjectContext) -> Dict[str, Any]:
    """
    Returns a flat dict merging every category's raw values (used by the
    Risk Engine) under a single `raw` key, plus a combined `display_metrics`
    list (used by the Report Builder for `calculated_metrics`).
    """
    timeline = compute_timeline_metrics(context)
    workload = compute_workload_metrics(context)
    productivity = compute_productivity_metrics(context)
    dependency = compute_dependency_and_confirmed_risk_metrics(context)

    display_metrics: List[CalculatedMetric] = (
        timeline["display_metrics"]
        + workload["display_metrics"]
        + productivity["display_metrics"]
        + dependency["display_metrics"]
    )

    raw = {
        **{k: v for k, v in timeline.items() if k != "display_metrics"},
        **{k: v for k, v in workload.items() if k != "display_metrics"},
        **{k: v for k, v in productivity.items() if k != "display_metrics"},
        **{k: v for k, v in dependency.items() if k != "display_metrics"},
    }

    return {"raw": raw, "display_metrics": display_metrics}
