"""
Deterministic productivity metrics: completion rate, task age, velocity
(tasks completed per recent period) from Task + TimeLog rows.
"""

from datetime import datetime, timezone, timedelta
from typing import List
from app.schemas.context_schema import ProjectContext
from app.schemas.report_schema import CalculatedMetric

VELOCITY_WINDOW_DAYS = 7


def compute_productivity_metrics(context: ProjectContext) -> dict:
    tasks = context.tasks
    now = datetime.now(timezone.utc)

    total_tasks = len(tasks)
    done_tasks = [t for t in tasks if t.status.value == "done"]
    progress_pct = round(len(done_tasks) / total_tasks * 100, 1) if total_tasks else None

    open_task_ages = [
        (now - t.created_at).days for t in tasks
        if t.status.value != "done" and t.created_at
    ]
    avg_task_age = round(sum(open_task_ages) / len(open_task_ages), 1) if open_task_ages else None

    window_start = now - timedelta(days=VELOCITY_WINDOW_DAYS)
    velocity = sum(
        1 for t in done_tasks
        if t.created_at and t.created_at >= window_start
    )

    effort_minutes = sum(tl.duration_minutes or 0 for tl in context.time_logs)
    effort_hours = round(effort_minutes / 60, 1)

    display_metrics: List[CalculatedMetric] = []
    if progress_pct is not None:
        display_metrics.append(CalculatedMetric(name="Project Progress", value=f"{progress_pct}%"))
    if avg_task_age is not None:
        display_metrics.append(CalculatedMetric(name="Average Open Task Age (days)", value=str(avg_task_age)))
    display_metrics.append(CalculatedMetric(name=f"Velocity (last {VELOCITY_WINDOW_DAYS}d)", value=str(velocity)))
    display_metrics.append(CalculatedMetric(name="Effort Consumed (hours)", value=str(effort_hours)))

    return {
        "progress_pct": progress_pct,
        "avg_task_age_days": avg_task_age,
        "velocity_last_period": velocity,
        "effort_hours_consumed": effort_hours,
        "display_metrics": display_metrics,
    }
