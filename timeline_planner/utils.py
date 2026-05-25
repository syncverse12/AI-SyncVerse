"""
utils.py
--------
Shared utility functions used across the planning module.

Covers
------
* Working-day calendar arithmetic (skip weekends).
* Hours ↔ working-day conversions.
* AI heuristic for estimating task duration when none is provided.
* Logging configuration helper.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Dict, List, Optional

from .models import Task, TaskPriority


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name: str = "planner") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


logger = get_logger()


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------

WORKING_DAYS: set = {0, 1, 2, 3, 4}   # Monday=0 … Friday=4


def is_working_day(d: date) -> bool:
    return d.weekday() in WORKING_DAYS


def next_working_day(d: date) -> date:
    """Return the next working day on or after *d*."""
    while not is_working_day(d):
        d += timedelta(days=1)
    return d


def add_working_days(start: date, working_days: float) -> date:
    """
    Advance *start* by *working_days* working days.

    Fractional days are rounded up so that partial-day tasks still
    consume a full calendar day.
    """
    full_days = math.ceil(working_days)
    current = next_working_day(start)
    added = 0
    while added < full_days:
        current += timedelta(days=1)
        if is_working_day(current):
            added += 1
    return current


def working_days_between(start: date, end: date) -> int:
    """Count working days in the half-open interval [start, end)."""
    count = 0
    current = start
    while current < end:
        if is_working_day(current):
            count += 1
        current += timedelta(days=1)
    return count


def hours_to_working_days(hours: float, hours_per_day: float = 8.0) -> float:
    return hours / hours_per_day


def working_days_to_hours(days: float, hours_per_day: float = 8.0) -> float:
    return days * hours_per_day


# ---------------------------------------------------------------------------
# AI Duration Estimator
# ---------------------------------------------------------------------------

# Base estimates (hours) indexed by rough keyword groups found in task names.
# This is a lightweight keyword heuristic — no ML model required.

_KEYWORD_ESTIMATES: List[tuple] = [
    # (keywords, base_hours)
    ({"design", "architect", "plan", "blueprint", "prototype"},    16.0),
    ({"research", "investigate", "analyse", "analyze", "spike"},   8.0),
    ({"implement", "develop", "build", "create", "code", "write"}, 24.0),
    ({"test", "qa", "review", "audit", "validate"},                12.0),
    ({"deploy", "release", "rollout", "launch"},                   8.0),
    ({"document", "docs", "readme", "spec"},                       6.0),
    ({"meeting", "sync", "standup", "demo", "presentation"},       2.0),
    ({"fix", "bug", "patch", "hotfix", "refactor"},               10.0),
    ({"migrate", "integration", "integrate"},                      20.0),
    ({"setup", "configure", "install", "onboard"},                 6.0),
]

_PRIORITY_MULTIPLIER: Dict[str, float] = {
    "low":      0.8,
    "medium":   1.0,
    "high":     1.2,
    "critical": 1.4,
}

_DEFAULT_HOURS = 8.0   # fallback when no keyword matches


def estimate_task_duration(task: Task) -> float:
    """
    Heuristic-based duration estimator.

    Algorithm
    ---------
    1. Tokenise the task name + description into lower-case words.
    2. Find the best-matching keyword group (most overlapping keywords).
    3. Apply a priority multiplier (critical tasks usually carry more scope).
    4. Scale by a complexity proxy: len(required_skills) adds 20 % per skill
       beyond the first, capped at 2×.

    Returns hours (float).
    """
    if task.is_milestone:
        return 0.0

    tokens = set(
        (task.name + " " + task.description).lower().split()
    )

    best_hours = _DEFAULT_HOURS
    best_overlap = 0

    for keywords, hours in _KEYWORD_ESTIMATES:
        overlap = len(keywords & tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_hours = hours

    # Priority multiplier
    priority_mult = _PRIORITY_MULTIPLIER.get(task.priority.value, 1.0)

    # Skill complexity multiplier: each additional skill beyond first adds 20 %
    skill_count = max(len(task.required_skills), 1)
    skill_mult = min(1.0 + 0.2 * (skill_count - 1), 2.0)

    estimated = best_hours * priority_mult * skill_mult
    logger.debug(
        "Estimated %s hours for task '%s' (priority=%s, skills=%d)",
        round(estimated, 1), task.name, task.priority.value, skill_count,
    )
    return round(estimated, 1)


def fill_missing_estimates(tasks: List[Task]) -> List[Task]:
    """
    Mutate tasks in-place: any task missing *estimated_hours* gets
    the AI-estimated value.  Returns the same list for chaining.
    """
    for task in tasks:
        if task.estimated_hours is None or task.estimated_hours <= 0:
            task.estimated_hours = estimate_task_duration(task)
    return tasks


# ---------------------------------------------------------------------------
# Resource capacity helpers
# ---------------------------------------------------------------------------

def total_resource_hours_for_period(
    resources,   # List[Resource]
    start: date,
    end: date,
    hours_per_day: float = 8.0,
) -> float:
    """
    Compute the aggregate available resource-hours in [start, end] inclusive.
    """
    total = 0.0
    day = start
    while day <= end:
        if is_working_day(day):
            for r in resources:
                total += r.effective_capacity_on(day) * hours_per_day
        day += timedelta(days=1)
    return total


# ---------------------------------------------------------------------------
# Formatting helpers (useful when building API responses)
# ---------------------------------------------------------------------------

def date_range_label(start: date, end: date) -> str:
    return f"{start.isoformat()} → {end.isoformat()}"


def format_duration(hours: float) -> str:
    days = hours / 8.0
    if days < 1:
        return f"{hours:.1f}h"
    return f"{days:.1f}d ({hours:.0f}h)"
