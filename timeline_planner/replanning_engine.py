"""
replanning_engine.py
--------------------
ReplanningEngine — processes real-world events and produces an updated
ProjectPlan with minimal disruption to the existing schedule.

Supported Events (EventType)
----------------------------
TASK_COMPLETED_EARLY          : actual_hours < estimated_hours
TASK_COMPLETED_LATE           : actual_hours > estimated_hours
TASK_ADDED                    : new Task injected into the plan
TASK_REMOVED                  : existing Task removed from the plan
RESOURCE_UNAVAILABLE          : resource becomes unavailable (e.g. sick leave)
RESOURCE_CAPACITY_CHANGED     : resource's capacity fraction changes
DEPENDENCY_CHANGED            : task's dependency list is replaced

Strategy
--------
1.  Apply the raw data mutation (update Task / Resource objects).
2.  Recalculate affected sub-graphs only (impact analysis) to minimise churn.
3.  Re-run CPM on the full graph to get updated critical path.
4.  Re-schedule only the tasks that changed or are downstream of the change.
5.  Regenerate sprints.
6.  Emit warnings if the deadline is now at risk.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Dict, List, Optional, Set

from .dependency_graph import DependencyGraph
from .models import (
    EventType,
    ProjectPlan,
    ReplanningEvent,
    Resource,
    Task,
    TaskStatus,
)
from .scheduler import SchedulingEngine
from .sprint_generator import SprintGenerator
from .utils import get_logger, next_working_day

logger = get_logger("planner.replanning")


class ReplanningEngine:
    """
    Accepts a ProjectPlan and a ReplanningEvent; returns an updated plan.

    Parameters
    ----------
    sprint_length_days : Passed through to SprintGenerator.
    hours_per_day      : Standard working hours per day.
    """

    def __init__(
        self,
        sprint_length_days: int = 14,
        hours_per_day: float = 8.0,
    ):
        self._sprint_length = sprint_length_days
        self._hours_per_day = hours_per_day

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recalculate_plan(
        self, plan: ProjectPlan, event: ReplanningEvent
    ) -> ProjectPlan:
        """
        Apply *event* to *plan* and return a new, updated ProjectPlan.
        The original plan object is not mutated.

        Parameters
        ----------
        plan  : The current ProjectPlan.
        event : The ReplanningEvent describing what changed.

        Returns
        -------
        Updated ProjectPlan.
        """
        # Deep-copy so the original remains intact
        new_plan = self._clone_plan(plan)
        new_plan.warnings = []

        logger.info("Replanning triggered by event: %s", event.event_type.value)

        # Dispatch to specific handler
        handlers = {
            EventType.TASK_COMPLETED_EARLY:        self._handle_task_completed,
            EventType.TASK_COMPLETED_LATE:         self._handle_task_completed,
            EventType.TASK_ADDED:                  self._handle_task_added,
            EventType.TASK_REMOVED:                self._handle_task_removed,
            EventType.RESOURCE_UNAVAILABLE:        self._handle_resource_unavailable,
            EventType.RESOURCE_CAPACITY_CHANGED:   self._handle_capacity_changed,
            EventType.DEPENDENCY_CHANGED:          self._handle_dependency_changed,
        }

        handler = handlers.get(event.event_type)
        if handler is None:
            new_plan.warnings.append(f"Unhandled event type: {event.event_type.value}")
            return new_plan

        affected_task_ids = handler(new_plan, event)

        # Rebuild graph, recompute CPM, reschedule affected tasks
        self._rebuild_schedule(new_plan, affected_task_ids)

        # Check deadline
        if new_plan.completion_date and new_plan.completion_date > new_plan.deadline:
            delta = (new_plan.completion_date - new_plan.deadline).days
            new_plan.warnings.append(
                f"⚠ Deadline at risk: estimated completion is {delta} day(s) late "
                f"({new_plan.completion_date.isoformat()} vs "
                f"deadline {new_plan.deadline.isoformat()})."
            )

        return new_plan

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_task_completed(
        self, plan: ProjectPlan, event: ReplanningEvent
    ) -> Set[str]:
        """
        Mark a task as completed (with actual hours), then reschedule all
        downstream tasks because their earliest start may have shifted.
        """
        task = plan.get_task(event.task_id or "")
        if task is None:
            plan.warnings.append(f"Task '{event.task_id}' not found; skipping.")
            return set()

        actual_hours = float(event.new_value or task.estimated_hours or 0.0)
        task.actual_hours = actual_hours
        task.status = TaskStatus.COMPLETED

        if event.event_type == EventType.TASK_COMPLETED_EARLY:
            logger.info(
                "Task '%s' completed early (%.1fh actual vs %.1fh estimated).",
                task.name, actual_hours, task.estimated_hours or 0.0,
            )
        else:
            logger.info(
                "Task '%s' completed late (%.1fh actual vs %.1fh estimated).",
                task.name, actual_hours, task.estimated_hours or 0.0,
            )
            # Adjust end_date to reflect actual completion
            if task.start_date:
                from .utils import add_working_days, hours_to_working_days
                days_taken = hours_to_working_days(actual_hours, self._hours_per_day)
                task.end_date = add_working_days(task.start_date, max(0, days_taken - 1))

        # All downstream tasks are affected
        graph = DependencyGraph(plan.tasks, self._hours_per_day)
        return graph.all_descendants(task.id)

    def _handle_task_added(
        self, plan: ProjectPlan, event: ReplanningEvent
    ) -> Set[str]:
        """Insert a new Task into the plan and reschedule its dependents."""
        new_task: Optional[Task] = event.new_value  # type: ignore[assignment]
        if not isinstance(new_task, Task):
            plan.warnings.append("TASK_ADDED event must carry a Task in new_value.")
            return set()

        plan.tasks.append(new_task)
        logger.info("Task '%s' added to plan.", new_task.name)

        # Affected = the new task + all its descendants (once graph rebuilt)
        affected = {new_task.id}
        try:
            graph = DependencyGraph(plan.tasks, self._hours_per_day)
            affected |= graph.all_descendants(new_task.id)
        except ValueError as exc:
            plan.warnings.append(str(exc))
        return affected

    def _handle_task_removed(
        self, plan: ProjectPlan, event: ReplanningEvent
    ) -> Set[str]:
        """Remove a task; reschedule tasks that depended on it."""
        task = plan.get_task(event.task_id or "")
        if task is None:
            plan.warnings.append(f"Task '{event.task_id}' not found; skipping.")
            return set()

        # Collect descendants before removal
        try:
            graph = DependencyGraph(plan.tasks, self._hours_per_day)
            affected = graph.all_descendants(task.id)
        except ValueError:
            affected = set()

        # Remove dependency references from other tasks
        for t in plan.tasks:
            if task.id in t.dependencies:
                t.dependencies.remove(task.id)

        plan.tasks = [t for t in plan.tasks if t.id != task.id]
        # Remove from sprints
        for sprint in plan.sprints:
            if task.id in sprint.task_ids:
                sprint.task_ids.remove(task.id)
                sprint.planned_hours -= task.estimated_hours or 0.0

        logger.info("Task '%s' removed from plan.", task.name)
        return affected

    def _handle_resource_unavailable(
        self, plan: ProjectPlan, event: ReplanningEvent
    ) -> Set[str]:
        """
        Mark a resource as no longer available.
        Reassign all their pending tasks and reschedule.
        """
        resource = plan.get_resource(event.resource_id or "")
        if resource is None:
            plan.warnings.append(
                f"Resource '{event.resource_id}' not found; skipping."
            )
            return set()

        # Make the resource completely unavailable
        resource.capacity = 0.0
        today = date.today()
        resource.available_until = today - timedelta(days=1)

        # Find all unfinished tasks assigned to this resource
        affected_ids: Set[str] = set()
        for task in plan.tasks:
            if task.assigned_to == resource.id and not task.is_complete:
                task.assigned_to = None  # will be re-assigned during reschedule
                affected_ids.add(task.id)
                # Descendants also need rescheduling
                graph = DependencyGraph(plan.tasks, self._hours_per_day)
                affected_ids |= graph.all_descendants(task.id)

        logger.warning(
            "Resource '%s' marked unavailable; %d tasks need reassignment.",
            resource.name, len(affected_ids),
        )
        return affected_ids

    def _handle_capacity_changed(
        self, plan: ProjectPlan, event: ReplanningEvent
    ) -> Set[str]:
        """Update a resource's capacity and reschedule their tasks."""
        resource = plan.get_resource(event.resource_id or "")
        if resource is None:
            plan.warnings.append(
                f"Resource '{event.resource_id}' not found; skipping."
            )
            return set()

        new_capacity = float(event.new_value or resource.capacity)
        old_capacity = resource.capacity
        resource.capacity = max(0.0, min(new_capacity, 1.0))

        logger.info(
            "Resource '%s' capacity changed: %.0f%% → %.0f%%.",
            resource.name, old_capacity * 100, resource.capacity * 100,
        )

        # Reschedule unfinished tasks assigned to this resource
        affected_ids: Set[str] = set()
        for task in plan.tasks:
            if task.assigned_to == resource.id and not task.is_complete:
                affected_ids.add(task.id)

        return affected_ids

    def _handle_dependency_changed(
        self, plan: ProjectPlan, event: ReplanningEvent
    ) -> Set[str]:
        """Replace a task's dependency list and reschedule the task + descendants."""
        task = plan.get_task(event.task_id or "")
        if task is None:
            plan.warnings.append(f"Task '{event.task_id}' not found; skipping.")
            return set()

        new_deps: List[str] = event.new_value or []  # type: ignore[assignment]
        task.dependencies = list(new_deps)
        logger.info(
            "Dependencies of task '%s' updated to: %s", task.name, new_deps
        )

        try:
            graph = DependencyGraph(plan.tasks, self._hours_per_day)
            affected = {task.id} | graph.all_descendants(task.id)
        except ValueError as exc:
            plan.warnings.append(str(exc))
            affected = {task.id}

        return affected

    # ------------------------------------------------------------------
    # Core reschedule routine
    # ------------------------------------------------------------------

    def _rebuild_schedule(
        self, plan: ProjectPlan, affected_ids: Set[str]
    ) -> None:
        """
        1.  Rebuild the dependency graph (validates integrity).
        2.  Recompute CPM → new critical path.
        3.  Reschedule only affected (non-completed) tasks.
        4.  Regenerate sprints.
        """
        try:
            graph = DependencyGraph(plan.tasks, self._hours_per_day)
        except ValueError as exc:
            plan.warnings.append(f"Graph error during rebuild: {exc}")
            return

        cpm_nodes, critical_path = graph.compute_cpm()
        plan.critical_path = critical_path

        # Determine project start (earliest scheduled date or today)
        completed_dates = [
            t.end_date for t in plan.tasks if t.is_complete and t.end_date
        ]
        if completed_dates:
            project_start = next_working_day(max(completed_dates) + timedelta(days=1))
        else:
            project_start = next_working_day(date.today())

        # Reset dates only for affected non-completed tasks
        for task in plan.tasks:
            if task.id in affected_ids and not task.is_complete:
                task.start_date = None
                task.end_date   = None
                task.sprint_id  = None

        engine = SchedulingEngine(
            resources=plan.resources,
            project_start=project_start,
            hours_per_day=self._hours_per_day,
        )

        topo_order = graph.topological_order()
        engine.schedule(plan.tasks, cpm_nodes, topo_order)

        # Regenerate sprints
        gen = SprintGenerator(
            sprint_length_days=self._sprint_length,
            hours_per_day=self._hours_per_day,
        )
        plan.sprints, plan.tasks = gen.generate_sprints(
            plan.tasks, plan.resources, critical_path
        )

    # ------------------------------------------------------------------
    # Clone helper
    # ------------------------------------------------------------------

    @staticmethod
    def _clone_plan(plan: ProjectPlan) -> ProjectPlan:
        """Return a deep copy of the plan."""
        return copy.deepcopy(plan)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"ReplanningEngine("
            f"sprint_length={self._sprint_length}d, "
            f"hours_per_day={self._hours_per_day})"
        )
