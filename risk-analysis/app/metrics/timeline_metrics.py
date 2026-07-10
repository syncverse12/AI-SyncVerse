"""
Deterministic timeline & milestone metrics. No AI here — pure calculation
from Timeline and Milestone rows in the ProjectContext.
"""

from datetime import datetime, timezone
from typing import List
from app.schemas.context_schema import ProjectContext
from app.schemas.report_schema import CalculatedMetric


def _now():
    return datetime.now(timezone.utc)


def compute_timeline_metrics(context: ProjectContext) -> dict:
    """
    Returns a dict of raw values (consumed by the Risk Engine) plus a list
    of display-ready CalculatedMetric objects (consumed by the Report Builder).
    """
    timelines = context.timeline
    milestones = context.milestones
    now = _now()

    days_remaining = None
    if timelines:
        due_dates = [t.due_date for t in timelines if t.due_date]
        if due_dates:
            nearest_due = min(due_dates)
            days_remaining = (nearest_due - now).days

    total_milestones = len(milestones)
    overdue_milestones = [
        m for m in milestones
        if m.target_date and m.target_date < now and (m.status or "").lower() != "done"
    ]
    done_milestones = [m for m in milestones if (m.status or "").lower() == "done"]

    milestone_completion_pct = (
        round(len(done_milestones) / total_milestones * 100, 1) if total_milestones else None
    )

    display_metrics: List[CalculatedMetric] = []
    if days_remaining is not None:
        display_metrics.append(CalculatedMetric(name="Days Remaining", value=str(days_remaining)))
    if milestone_completion_pct is not None:
        display_metrics.append(
            CalculatedMetric(name="Milestone Completion", value=f"{milestone_completion_pct}%")
        )
    display_metrics.append(
        CalculatedMetric(name="Overdue Milestones", value=str(len(overdue_milestones)))
    )

    return {
        "days_remaining": days_remaining,
        "total_milestones": total_milestones,
        "overdue_milestones_count": len(overdue_milestones),
        "milestone_completion_pct": milestone_completion_pct,
        "display_metrics": display_metrics,
    }
