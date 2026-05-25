"""
sprint_generator.py
-------------------
SprintGenerator — groups scheduled tasks into time-boxed sprints.

Algorithm
---------
1.  Accept fully scheduled tasks (each has start_date / end_date).
2.  Determine sprint boundaries:
    a. Default sprint length is configurable (default 14 calendar days / 2 weeks).
    b. Sprints start on the earliest task start date and advance by
       *sprint_days* until the project completion date.
3.  Assign each task to the sprint whose window contains its start_date.
    Tasks that span sprint boundaries are placed in the sprint where
    they *start* (common real-world practice).
4.  Heuristic adjustments:
    a. If a sprint would exceed *max_load_ratio* (default 0.9), overflow
       tasks are deferred to the next sprint.
    b. Critical-path tasks are never deferred.
5.  Compute per-sprint capacity_hours and planned_hours.
6.  Return ordered Sprint list and updated Task list.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from .models import Resource, Sprint, Task
from .utils import (
    get_logger,
    next_working_day,
    total_resource_hours_for_period,
    working_days_between,
)

logger = get_logger("planner.sprint_generator")


class SprintGenerator:
    """
    Converts a flat list of scheduled tasks into a sprint structure.

    Parameters
    ----------
    sprint_length_days : Calendar length of each sprint (default 14).
    hours_per_day      : Working hours per day (default 8).
    max_load_ratio     : Maximum allowed sprint load as a fraction of total
                         capacity before deferral kicks in (default 0.9).
    """

    def __init__(
        self,
        sprint_length_days: int = 14,
        hours_per_day: float = 8.0,
        max_load_ratio: float = 0.90,
    ):
        self._sprint_length = sprint_length_days
        self._hours_per_day = hours_per_day
        self._max_load_ratio = max_load_ratio

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_sprints(
        self,
        tasks: List[Task],
        resources: List[Resource],
        critical_path: List[str],
        project_start: Optional[date] = None,
    ) -> Tuple[List[Sprint], List[Task]]:
        """
        Generate sprints for *tasks*.

        Returns
        -------
        sprints : Ordered list of Sprint objects.
        tasks   : The same list with sprint_id fields populated.
        """
        scheduled = [t for t in tasks if t.start_date and not t.is_complete]
        completed = [t for t in tasks if t.is_complete]

        if not scheduled:
            logger.info("No scheduled tasks to group into sprints.")
            return [], tasks

        critical_ids = set(critical_path)

        # Determine sprint window boundaries
        sprint_windows = self._build_sprint_windows(scheduled, project_start)

        sprints: List[Sprint] = []
        task_map: Dict[str, Task] = {t.id: t for t in scheduled}

        # Sort tasks: critical first, then by start_date, then by priority
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        scheduled_sorted = sorted(
            scheduled,
            key=lambda t: (
                0 if t.id in critical_ids else 1,
                t.start_date or date.max,
                priority_rank.get(t.priority.value, 2),
            ),
        )

        # Track which tasks have been assigned to a sprint
        assigned: Dict[str, int] = {}  # task_id → sprint_id

        for sprint_num, (win_start, win_end) in enumerate(sprint_windows, start=1):
            sprint_capacity = total_resource_hours_for_period(
                resources, win_start, win_end, self._hours_per_day
            )
            sprint = Sprint(
                id=sprint_num,
                start_date=win_start,
                end_date=win_end,
                capacity_hours=sprint_capacity,
            )
            sprints.append(sprint)

        # Assign tasks to sprints using a greedy heuristic
        for task in scheduled_sorted:
            if not task.start_date:
                continue

            target_sprint_idx = self._find_target_sprint(
                task.start_date, sprint_windows
            )
            if target_sprint_idx is None:
                # Task falls outside all sprint windows — assign to last sprint
                target_sprint_idx = len(sprints) - 1

            is_critical = task.id in critical_ids

            # Attempt to place task; defer if over capacity (non-critical only)
            placed = False
            for offset in range(len(sprints) - target_sprint_idx):
                idx = target_sprint_idx + offset
                if idx >= len(sprints):
                    break
                sprint = sprints[idx]
                task_hours = task.estimated_hours or 0.0
                projected_load = sprint.planned_hours + task_hours
                load_ratio = (
                    projected_load / sprint.capacity_hours
                    if sprint.capacity_hours > 0
                    else float("inf")
                )

                if is_critical or load_ratio <= self._max_load_ratio:
                    sprint.task_ids.append(task.id)
                    sprint.planned_hours += task_hours
                    assigned[task.id] = sprint.id
                    task.sprint_id = sprint.id
                    placed = True
                    break

            if not placed:
                # Force into last sprint (avoid losing tasks)
                last = sprints[-1]
                last.task_ids.append(task.id)
                last.planned_hours += task.estimated_hours or 0.0
                assigned[task.id] = last.id
                task.sprint_id = last.id

                if not is_critical:
                    logger.warning(
                        "Sprint %d over capacity: task '%s' force-placed.",
                        last.id, task.name,
                    )

        # Restore completed tasks (no sprint assignment change needed)
        all_tasks = scheduled + completed
        return sprints, all_tasks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_sprint_windows(
        self,
        tasks: List[Task],
        project_start: Optional[date],
    ) -> List[Tuple[date, date]]:
        """
        Build a list of (sprint_start, sprint_end) tuples covering the
        entire project timeline.
        """
        if project_start:
            first_day = next_working_day(project_start)
        else:
            first_day = min(
                (t.start_date for t in tasks if t.start_date), default=date.today()
            )
            first_day = next_working_day(first_day)

        last_day = max(
            (t.end_date for t in tasks if t.end_date), default=first_day
        )

        windows: List[Tuple[date, date]] = []
        current = first_day
        while current <= last_day:
            win_end = current + timedelta(days=self._sprint_length - 1)
            # Don't let the last sprint window start after the last task ends
            windows.append((current, win_end))
            current = win_end + timedelta(days=1)
            # Snap to next working day to avoid orphaned weekends
            current = next_working_day(current)

        return windows

    def _find_target_sprint(
        self,
        task_start: date,
        windows: List[Tuple[date, date]],
    ) -> Optional[int]:
        """Return the 0-based index of the sprint window containing task_start."""
        for idx, (win_start, win_end) in enumerate(windows):
            if win_start <= task_start <= win_end:
                return idx
        # If task_start is before first window (shouldn't happen), use sprint 0
        if task_start < windows[0][0]:
            return 0
        return None   # past last window

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"SprintGenerator("
            f"sprint_length={self._sprint_length}d, "
            f"max_load={self._max_load_ratio:.0%})"
        )
