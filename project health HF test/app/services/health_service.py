"""
app/services/health_service.py
Layer 1 – Project Health Score (execution performance).
"""
from __future__ import annotations

from datetime import date
from typing import List

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.domain import (
    DelayedTask,
    GoalProgressItem,
    HealthScoreResult,
    Priority,
    PRIORITY_MULTIPLIER,
    Project,
    TaskStatus,
)

logger = get_logger(__name__)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def compute_health_score(project: Project) -> HealthScoreResult:
    """
    Compute the three-component health score for a project:
      1. Completion Rate
      2. Goal Progress (weighted)
      3. Efficiency Score
      4. Delay Impact Score
    """
    settings = get_settings()
    today = date.today()
    tasks = project.tasks
    total = len(tasks)

    # ── 1. Completion Rate ────────────────────────────────────────────────────
    completed_tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]
    completion_rate = len(completed_tasks) / total if total else 0.0

    # ── 2. Goal Progress (weighted) ──────────────────────────────────────────
    goal_details: List[GoalProgressItem] = []
    total_goal_weight = sum(g.weight for g in project.goals) or 1.0

    for goal in project.goals:
        g_tasks = [t for t in tasks if t.goal_id == goal.id]
        g_total = len(g_tasks)
        g_done = len([t for t in g_tasks if t.status == TaskStatus.COMPLETED])
        progress = g_done / g_total if g_total else 0.0
        goal_details.append(GoalProgressItem(
            goal_id=goal.id,
            title=goal.title,
            weight=goal.weight,
            progress=progress,
            completed_tasks=g_done,
            total_tasks=g_total,
        ))

    weighted_goal_progress = sum(
        (g.progress * g.weight / total_goal_weight) for g in goal_details
    )

    # ── 3. Delay Impact Score ─────────────────────────────────────────────────
    delayed: List[DelayedTask] = []
    for task in tasks:
        if task.status == TaskStatus.COMPLETED:
            continue
        if task.deadline and task.deadline < today:
            delay_days = (today - task.deadline).days
            multiplier = PRIORITY_MULTIPLIER.get(task.priority, 1.0)
            contribution = delay_days * multiplier
            delayed.append(DelayedTask(
                task_id=task.id,
                title=task.title,
                delay_days=delay_days,
                priority=task.priority,
                delay_contribution=contribution,
            ))

    raw_delay_score = sum(d.delay_contribution for d in delayed)
    # Normalise delay: cap at 500 → maps to 0–1 range
    delay_score_normalized = min(raw_delay_score / 500.0, 1.0)

    # ── 4. Efficiency Score ───────────────────────────────────────────────────
    efficiency_ratios = []
    for task in completed_tasks:
        if task.estimated_hours and task.actual_hours and task.actual_hours > 0:
            efficiency_ratios.append(task.estimated_hours / task.actual_hours)

    efficiency_score = sum(efficiency_ratios) / len(efficiency_ratios) if efficiency_ratios else 1.0
    efficiency_score = min(efficiency_score, 2.0) / 2.0  # Normalise to 0–1

    # ── Final Health Score ────────────────────────────────────────────────────
    w = settings
    raw = (
        w.health_weight_goal_progress * weighted_goal_progress
        + w.health_weight_completion_rate * completion_rate
        + w.health_weight_efficiency * efficiency_score
        - w.health_weight_delay * delay_score_normalized
    )
    health_score = _clamp(raw * 100)

    logger.info(
        "health_score_computed",
        project_id=project.id,
        health_score=round(health_score, 2),
        delayed_tasks=len(delayed),
    )

    return HealthScoreResult(
        project_id=project.id,
        health_score=round(health_score, 2),
        completion_rate=round(completion_rate * 100, 2),
        goal_progress=round(weighted_goal_progress * 100, 2),
        efficiency_score=round(efficiency_score * 100, 2),
        delay_score=round(raw_delay_score, 2),
        delayed_tasks=delayed,
        goal_details=goal_details,
        score_breakdown={
            "goal_progress_contribution": round(
                w.health_weight_goal_progress * weighted_goal_progress * 100, 2
            ),
            "completion_rate_contribution": round(
                w.health_weight_completion_rate * completion_rate * 100, 2
            ),
            "efficiency_contribution": round(
                w.health_weight_efficiency * efficiency_score * 100, 2
            ),
            "delay_penalty": round(
                w.health_weight_delay * delay_score_normalized * 100, 2
            ),
        },
    )
