"""
Deterministic dependency & confirmed-risk metrics: blocked tasks (self-join
on Task.depend_on) and the manually-logged Risks table, which is ground
truth and gets folded into the Overall Risk directly.
"""

from typing import List
from app.schemas.context_schema import ProjectContext
from app.schemas.report_schema import CalculatedMetric

SEVERITY_WEIGHT = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def compute_dependency_and_confirmed_risk_metrics(context: ProjectContext) -> dict:
    tasks = context.tasks
    done_task_ids = {t.task_id for t in tasks if t.status.value == "done"}

    blocked_tasks = [
        t for t in tasks
        if t.status.value != "done"
        and any(dep_id not in done_task_ids for dep_id in t.depends_on_task_ids)
    ]

    open_confirmed_risks = [r for r in context.confirmed_risks if (r.status or "").lower() != "closed"]
    confirmed_risk_load = sum(SEVERITY_WEIGHT.get(r.severity.value, 1) for r in open_confirmed_risks)

    meeting_count = len(context.meetings)

    display_metrics: List[CalculatedMetric] = []
    display_metrics.append(CalculatedMetric(name="Blocked Tasks", value=str(len(blocked_tasks))))
    display_metrics.append(CalculatedMetric(name="Open Confirmed Risks", value=str(len(open_confirmed_risks))))
    display_metrics.append(CalculatedMetric(name="Recent Meeting Count", value=str(meeting_count)))

    return {
        "blocked_tasks_count": len(blocked_tasks),
        "open_confirmed_risks": open_confirmed_risks,
        "confirmed_risk_load": confirmed_risk_load,
        "meeting_count": meeting_count,
        "display_metrics": display_metrics,
    }
