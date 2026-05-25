"""
scheduler.py
------------
SchedulingEngine — converts an ordered task list + CPM analysis into
concrete start/end calendar dates while respecting resource availability
and capacity constraints (resource levelling).

Algorithm overview
------------------
1.  Accept tasks in topological order (dependency-safe).
2.  For each task:
    a. Determine the earliest possible start date:
       max(project_start, max(predecessor.end_date + 1 working day))
    b. Find the best-fit available resource (skill match + least loaded).
    c. Compute the end date from estimated_hours and resource capacity.
    d. Advance a per-resource load tracker to avoid over-allocation.
3.  Resource levelling: if a resource is at capacity for a given day,
    push the task start to the next available slot.
4.  Return the fully annotated task list.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from .dependency_graph import CPMNode, DependencyGraph
from .models import Resource, Task
from .utils import (
    add_working_days,
    get_logger,
    hours_to_working_days,
    is_working_day,
    next_working_day,
)

logger = get_logger("planner.scheduler")


# ---------------------------------------------------------------------------
# Resource Load Tracker
# ---------------------------------------------------------------------------

class ResourceLoadTracker:
    """
    Tracks committed hours per resource per calendar day.
    Used to enforce capacity constraints during scheduling.
    """

    def __init__(self, resources: List[Resource], hours_per_day: float = 8.0):
        self._resources = {r.id: r for r in resources}
        self._hours_per_day = hours_per_day
        # { resource_id: { date: committed_hours } }
        self._load: Dict[str, Dict[date, float]] = defaultdict(lambda: defaultdict(float))

    def available_hours_on(self, resource_id: str, day: date) -> float:
        resource = self._resources.get(resource_id)
        if resource is None or not resource.is_available_on(day):
            return 0.0
        capacity = resource.capacity * self._hours_per_day
        committed = self._load[resource_id].get(day, 0.0)
        return max(capacity - committed, 0.0)

    def commit(self, resource_id: str, start: date, end: date, total_hours: float) -> None:
        """Spread *total_hours* evenly across working days in [start, end]."""
        working_days = self._working_days_list(start, end)
        if not working_days:
            return
        resource = self._resources.get(resource_id)
        if resource is None:
            return

        hours_per_working_day = resource.capacity * self._hours_per_day
        remaining = total_hours
        for day in working_days:
            if remaining <= 0:
                break
            available = self.available_hours_on(resource_id, day)
            allocated = min(available, remaining, hours_per_working_day)
            self._load[resource_id][day] += allocated
            remaining -= allocated

    def first_available_date(
        self, resource_id: str, earliest: date, required_daily_hours: float
    ) -> date:
        """
        Return the first working day on or after *earliest* where this
        resource has at least *required_daily_hours* of free capacity.
        """
        day = next_working_day(earliest)
        for _ in range(365):   # safety cap — avoid infinite loops
            avail = self.available_hours_on(resource_id, day)
            if avail >= required_daily_hours - 1e-6:
                return day
            day += timedelta(days=1)
            while not is_working_day(day):
                day += timedelta(days=1)
        return day   # best effort

    @staticmethod
    def _working_days_list(start: date, end: date) -> List[date]:
        days = []
        d = start
        while d <= end:
            if is_working_day(d):
                days.append(d)
            d += timedelta(days=1)
        return days


# ---------------------------------------------------------------------------
# SchedulingEngine
# ---------------------------------------------------------------------------

class SchedulingEngine:
    """
    Maps an ordered sequence of tasks onto a real calendar, assigning
    resources and computing start/end dates.

    Parameters
    ----------
    resources     : All available project resources.
    project_start : First possible working day for any task.
    hours_per_day : Standard working hours in a day (default 8).
    """

    def __init__(
        self,
        resources: List[Resource],
        project_start: date,
        hours_per_day: float = 8.0,
    ):
        self._resources = resources
        self._project_start = next_working_day(project_start)
        self._hours_per_day = hours_per_day
        self._load_tracker = ResourceLoadTracker(resources, hours_per_day)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def schedule(
        self,
        tasks: List[Task],
        cpm_nodes: Dict[str, CPMNode],
        topo_order: List[str],
    ) -> List[Task]:
        """
        Assign start_date, end_date, and assigned_to for each task.

        Returns the same list (mutated in-place) for convenience.
        """
        task_map: Dict[str, Task] = {t.id: t for t in tasks}
        scheduled: Set[str] = set()

        for tid in topo_order:
            task = task_map.get(tid)
            if task is None:
                continue
            if task.is_complete:
                # Already done — keep its existing dates but mark as scheduled
                scheduled.add(tid)
                continue

            earliest_start = self._earliest_start(task, task_map, scheduled)
            resource = self._pick_resource(task, earliest_start)

            if resource is not None:
                start, end = self._compute_dates_with_resource(
                    task, resource, earliest_start
                )
                task.assigned_to = resource.id
                self._load_tracker.commit(resource.id, start, end, task.estimated_hours or 0.0)
            else:
                # No matching resource — schedule without assignment
                logger.warning(
                    "No available resource found for task '%s'. Scheduling unassigned.",
                    task.name,
                )
                start = earliest_start
                end = self._compute_end_date_unresourced(task, start)

            task.start_date = start
            task.end_date   = end
            scheduled.add(tid)

        return tasks

    def allocate_resources(self, tasks: List[Task]) -> List[Task]:
        """
        Standalone resource allocation pass for already-scheduled tasks
        that are missing an assignment.  Useful after replanning.
        """
        for task in tasks:
            if task.assigned_to or task.is_complete or not task.start_date:
                continue
            resource = self._pick_resource(task, task.start_date)
            if resource:
                task.assigned_to = resource.id
                self._load_tracker.commit(
                    resource.id,
                    task.start_date,
                    task.end_date or task.start_date,
                    task.estimated_hours or 0.0,
                )
        return tasks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _earliest_start(
        self, task: Task, task_map: Dict[str, Task], scheduled: Set[str]
    ) -> date:
        """
        Earliest start = max(project_start, day after all predecessors finish).
        """
        earliest = self._project_start
        for dep_id in task.dependencies:
            dep = task_map.get(dep_id)
            if dep and dep.end_date:
                # Start the day *after* dependency finishes
                candidate = dep.end_date + timedelta(days=1)
                candidate = next_working_day(candidate)
                if candidate > earliest:
                    earliest = candidate
        return earliest

    def _pick_resource(
        self, task: Task, earliest_start: date
    ) -> Optional[Resource]:
        """
        Select the most suitable available resource for a task.

        Scoring (higher = better)
        -------------------------
        * +2 per matching skill in required_skills
        * −load_ratio  (prefer less-loaded resources)
        * resource must be available on earliest_start
        """
        if not self._resources:
            return None

        best_resource: Optional[Resource] = None
        best_score = float("-inf")

        for resource in self._resources:
            if not resource.is_available_on(earliest_start):
                continue

            # Skill match score
            skill_score = len(
                set(task.required_skills) & set(resource.skills)
            ) * 2.0

            # Load ratio penalty (over the next 5 working days)
            load_score = self._load_ratio_score(resource.id, earliest_start)

            score = skill_score - load_score

            if score > best_score:
                best_score = score
                best_resource = resource

        return best_resource

    def _load_ratio_score(self, resource_id: str, from_date: date) -> float:
        """
        Returns a 0–1 load ratio (0 = free, 1 = fully booked) over a
        5-working-day lookahead window.  Used as a penalty in resource scoring.
        """
        resource = next((r for r in self._resources if r.id == resource_id), None)
        if resource is None:
            return 1.0
        total_capacity = 0.0
        total_committed = 0.0
        day = from_date
        days_counted = 0
        while days_counted < 5:
            if is_working_day(day):
                cap = resource.capacity * self._hours_per_day
                committed = self._load_tracker._load[resource_id].get(day, 0.0)
                total_capacity += cap
                total_committed += committed
                days_counted += 1
            day += timedelta(days=1)
        if total_capacity == 0:
            return 1.0
        return total_committed / total_capacity

    def _compute_dates_with_resource(
        self, task: Task, resource: Resource, earliest_start: date
    ) -> Tuple[date, date]:
        """
        Given a resource and an earliest start, find the first date where
        the resource has capacity, then calculate the end date.
        """
        hours = task.estimated_hours or self._hours_per_day
        daily_capacity = resource.capacity * self._hours_per_day

        # Find first date with sufficient capacity
        start = self._load_tracker.first_available_date(
            resource.id, earliest_start, min(daily_capacity, hours)
        )

        # Number of working days needed
        working_days_needed = math.ceil(hours / max(daily_capacity, 1e-6))
        end = add_working_days(start, working_days_needed - 1)
        # end should not go before start
        if end < start:
            end = start

        return start, end

    def _compute_end_date_unresourced(self, task: Task, start: date) -> date:
        """Fallback end date when no resource is available (assume 1 FTE)."""
        hours = task.estimated_hours or self._hours_per_day
        days_needed = max(1, math.ceil(hours / self._hours_per_day))
        return add_working_days(start, days_needed - 1)
