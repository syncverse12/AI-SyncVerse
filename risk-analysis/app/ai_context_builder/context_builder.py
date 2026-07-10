"""
Converts raw ProjectContext + computed metrics into a compact, clean
summary dict — never raw table rows — before it's handed to the prompt
builder. This is what actually gets sent to the LLM.
"""

from typing import Any, Dict
from app.schemas.context_schema import ProjectContext


def build_context_summary(context: ProjectContext, raw_metrics: Dict[str, Any]) -> dict:
    project = context.project

    return {
        "project": {
            "name": project.project_name,
            "priority": project.priority,
            "status": project.status,
            "budget": project.budget,
        },
        "timeline": {
            "days_remaining": raw_metrics.get("days_remaining"),
            "milestones_done_pct": raw_metrics.get("milestone_completion_pct"),
            "overdue_milestones": raw_metrics.get("overdue_milestones_count"),
        },
        "tasks": {
            "total": len(context.tasks),
            "progress_pct": raw_metrics.get("progress_pct"),
            "blocked_by_dependency": raw_metrics.get("blocked_tasks_count"),
            "average_open_task_age_days": raw_metrics.get("avg_task_age_days"),
        },
        "workload": {
            "avg_ratio": raw_metrics.get("avg_workload_ratio"),
            "overloaded_members": raw_metrics.get("overloaded_members_count"),
            "team_size": raw_metrics.get("team_size"),
        },
        "productivity": {
            "velocity_last_period": raw_metrics.get("velocity_last_period"),
            "effort_hours_consumed": raw_metrics.get("effort_hours_consumed"),
        },
        "communication": {
            "recent_meeting_count": raw_metrics.get("meeting_count"),
        },
        "confirmed_risks": [
            {"name": r.risk_name, "severity": r.severity.value, "status": r.status}
            for r in raw_metrics.get("open_confirmed_risks", [])
        ],
        "data_completeness": context.data_completeness,
        "missing_sources": context.missing_sources,
    }
