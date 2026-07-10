"""
Deterministic resource / workload metrics computed from Task assignments
and User.task_capacity. task_capacity's unit isn't defined in the schema,
so we treat it as a *relative* load score (per Phase 1 analysis) rather
than an absolute number of hours.
"""

from typing import List
from app.schemas.context_schema import ProjectContext
from app.schemas.report_schema import CalculatedMetric


def compute_workload_metrics(context: ProjectContext) -> dict:
    tasks = context.tasks
    members = context.team_members

    assigned_counts: dict = {}
    for task in tasks:
        if task.assigned_user_id:
            assigned_counts[task.assigned_user_id] = assigned_counts.get(task.assigned_user_id, 0) + 1

    ratios: List[float] = []
    overloaded_members = 0
    for member in members:
        assigned = assigned_counts.get(member.user_id, member.assigned_task_count)
        capacity = member.task_capacity or 1.0
        ratio = assigned / capacity if capacity else float(assigned)
        ratios.append(ratio)
        if ratio > 1.2:  # assigned load noticeably exceeds stated capacity
            overloaded_members += 1

    avg_ratio = round(sum(ratios) / len(ratios), 2) if ratios else None
    team_size = len(members)

    display_metrics: List[CalculatedMetric] = []
    if avg_ratio is not None:
        display_metrics.append(CalculatedMetric(name="Average Workload Ratio", value=str(avg_ratio)))
    display_metrics.append(CalculatedMetric(name="Overloaded Members", value=str(overloaded_members)))
    display_metrics.append(CalculatedMetric(name="Team Size", value=str(team_size)))

    return {
        "avg_workload_ratio": avg_ratio,
        "overloaded_members_count": overloaded_members,
        "team_size": team_size,
        "display_metrics": display_metrics,
    }
