"""
planner.py   (ProjectPlanner)
------------------------------
High-level facade that wires together all sub-components:
    DependencyGraph → CPM → SchedulingEngine → SprintGenerator

This is the single entry point for FastAPI routes or any other caller.
All methods return plain Python objects (ProjectPlan, Sprint, Task, …)
that can be serialised to JSON via their .to_dict() methods.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from .dependency_graph import DependencyGraph
from .models import ProjectPlan, ReplanningEvent, Resource, Sprint, Task
from .replanning_engine import ReplanningEngine
from .scheduler import SchedulingEngine
from .sprint_generator import SprintGenerator
from .utils import fill_missing_estimates, get_logger

logger = get_logger("planner.core")


class ProjectPlanner:
    """
    Orchestrates the full planning pipeline.

    Parameters
    ----------
    project_name       : Human-readable project label.
    deadline           : Hard deadline the plan must respect.
    tasks              : Initial list of Task objects.
    resources          : Available team members / resources.
    project_start      : Earliest possible start date (defaults to today).
    sprint_length_days : Sprint duration in calendar days (default 14).
    hours_per_day      : Standard working hours per day (default 8).
    """

    def __init__(
        self,
        project_name: str,
        deadline: date,
        tasks: List[Task],
        resources: List[Resource],
        project_start: Optional[date] = None,
        sprint_length_days: int = 14,
        hours_per_day: float = 8.0,
    ):
        self.project_name = project_name
        self.deadline = deadline
        self.tasks = tasks
        self.resources = resources
        self.project_start = project_start or date.today()
        self.sprint_length_days = sprint_length_days
        self.hours_per_day = hours_per_day

        # Latest plan — set after build_initial_plan()
        self._current_plan: Optional[ProjectPlan] = None
        self._replanning_engine = ReplanningEngine(
            sprint_length_days=sprint_length_days,
            hours_per_day=hours_per_day,
        )

    # ------------------------------------------------------------------
    # 1. Build Initial Plan
    # ------------------------------------------------------------------

    def build_initial_plan(self) -> ProjectPlan:
        """
        Full planning pipeline:
          1. Fill missing duration estimates (AI heuristic).
          2. Build dependency graph + validate DAG.
          3. Run CPM → determine critical path.
          4. Schedule tasks onto calendar with resource levelling.
          5. Group tasks into sprints.
          6. Return a ProjectPlan.

        Returns
        -------
        ProjectPlan — fully populated and ready to serialise.
        """
        logger.info("Building initial plan for project '%s'…", self.project_name)

        # Step 1 — estimate missing durations
        fill_missing_estimates(self.tasks)

        # Step 2 — build and validate the dependency graph
        try:
            graph = DependencyGraph(self.tasks, self.hours_per_day)
        except ValueError as exc:
            raise ValueError(f"Invalid dependency graph: {exc}") from exc

        # Step 3 — CPM analysis
        cpm_nodes, critical_path = graph.compute_cpm()
        logger.info(
            "Critical path (%d tasks): %s",
            len(critical_path),
            " → ".join(critical_path[:8]) + ("…" if len(critical_path) > 8 else ""),
        )

        # Step 4 — schedule tasks onto the calendar
        scheduler = SchedulingEngine(
            resources=self.resources,
            project_start=self.project_start,
            hours_per_day=self.hours_per_day,
        )
        topo_order = graph.topological_order()
        scheduled_tasks = scheduler.schedule(self.tasks, cpm_nodes, topo_order)

        # Step 5 — sprint grouping
        sprint_gen = SprintGenerator(
            sprint_length_days=self.sprint_length_days,
            hours_per_day=self.hours_per_day,
        )
        sprints, all_tasks = sprint_gen.generate_sprints(
            scheduled_tasks, self.resources, critical_path, self.project_start
        )

        # Step 6 — assemble ProjectPlan
        warnings: List[str] = []
        plan = ProjectPlan(
            project_name=self.project_name,
            deadline=self.deadline,
            tasks=all_tasks,
            sprints=sprints,
            resources=self.resources,
            critical_path=critical_path,
            warnings=warnings,
        )

        # Deadline check
        if plan.completion_date and plan.completion_date > self.deadline:
            delta = (plan.completion_date - self.deadline).days
            plan.warnings.append(
                f"⚠ Deadline risk: estimated completion "
                f"{plan.completion_date.isoformat()} is {delta} day(s) past "
                f"the deadline {self.deadline.isoformat()}."
            )
        else:
            logger.info("Plan is on schedule ✓  (completion %s)", plan.completion_date)

        self._current_plan = plan
        logger.info(
            "Plan built: %d tasks, %d sprints, %d resources.",
            len(all_tasks), len(sprints), len(self.resources),
        )
        return plan

    # ------------------------------------------------------------------
    # 2. Generate Sprints (standalone — e.g. after external scheduling)
    # ------------------------------------------------------------------

    def generate_sprints(
        self,
        tasks: Optional[List[Task]] = None,
        resources: Optional[List[Resource]] = None,
        critical_path: Optional[List[str]] = None,
    ) -> List[Sprint]:
        """
        (Re)generate sprints from an already-scheduled task list.
        Falls back to the current plan's values when args are omitted.

        Returns
        -------
        List[Sprint] — updated sprint structure.
        """
        tasks     = tasks     or (self._current_plan.tasks     if self._current_plan else self.tasks)
        resources = resources or (self._current_plan.resources if self._current_plan else self.resources)
        cp        = critical_path or (self._current_plan.critical_path if self._current_plan else [])

        gen = SprintGenerator(
            sprint_length_days=self.sprint_length_days,
            hours_per_day=self.hours_per_day,
        )
        sprints, updated_tasks = gen.generate_sprints(
            tasks, resources, cp, self.project_start
        )

        if self._current_plan:
            self._current_plan.sprints = sprints
            self._current_plan.tasks   = updated_tasks

        return sprints

    # ------------------------------------------------------------------
    # 3. Dynamic Replanning
    # ------------------------------------------------------------------

    def recalculate_plan(self, event: ReplanningEvent) -> ProjectPlan:
        """
        Apply a real-world event to the current plan and return an
        updated ProjectPlan.

        Parameters
        ----------
        event : ReplanningEvent describing the change.

        Returns
        -------
        Updated ProjectPlan (the old plan is preserved internally for diff).

        Raises
        ------
        RuntimeError : if called before build_initial_plan().
        """
        if self._current_plan is None:
            raise RuntimeError(
                "No initial plan exists. Call build_initial_plan() first."
            )

        updated_plan = self._replanning_engine.recalculate_plan(
            self._current_plan, event
        )
        self._current_plan = updated_plan
        return updated_plan

    # ------------------------------------------------------------------
    # 4. Update Dependencies
    # ------------------------------------------------------------------

    def update_dependencies(
        self, task_id: str, new_dependencies: List[str]
    ) -> ProjectPlan:
        """
        Replace the dependency list of *task_id* and trigger a replan.

        Parameters
        ----------
        task_id          : ID of the task whose deps are changing.
        new_dependencies : New list of prerequisite task IDs.

        Returns
        -------
        Updated ProjectPlan.
        """
        from .models import EventType

        event = ReplanningEvent(
            event_type=EventType.DEPENDENCY_CHANGED,
            task_id=task_id,
            new_value=new_dependencies,
        )
        return self.recalculate_plan(event)

    # ------------------------------------------------------------------
    # 5. Allocate Resources (standalone pass)
    # ------------------------------------------------------------------

    def allocate_resources(
        self,
        tasks: Optional[List[Task]] = None,
        resources: Optional[List[Resource]] = None,
    ) -> List[Task]:
        """
        Assign resources to any unassigned (but scheduled) tasks.
        Useful as a post-processing step or after partial replanning.

        Returns
        -------
        Updated list of Task objects.
        """
        tasks     = tasks     or (self._current_plan.tasks     if self._current_plan else self.tasks)
        resources = resources or (self._current_plan.resources if self._current_plan else self.resources)

        scheduler = SchedulingEngine(
            resources=resources,
            project_start=self.project_start,
            hours_per_day=self.hours_per_day,
        )
        updated = scheduler.allocate_resources(tasks)

        if self._current_plan:
            self._current_plan.tasks = updated

        return updated

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def current_plan(self) -> Optional[ProjectPlan]:
        """The most recently generated / updated ProjectPlan."""
        return self._current_plan

    def get_task_by_name(self, name: str) -> Optional[Task]:
        if not self._current_plan:
            return None
        return next(
            (t for t in self._current_plan.tasks if t.name.lower() == name.lower()),
            None,
        )

    def summary(self) -> Dict:
        """
        Return a concise summary dict — handy for API health-check endpoints.
        """
        plan = self._current_plan
        if plan is None:
            return {"status": "no_plan"}
        return {
            "project_name": plan.project_name,
            "deadline": plan.deadline.isoformat(),
            "is_on_time": plan.is_on_time,
            "completion_date": (
                plan.completion_date.isoformat() if plan.completion_date else None
            ),
            "total_tasks": len(plan.tasks),
            "total_sprints": len(plan.sprints),
            "total_resources": len(plan.resources),
            "critical_path_length": len(plan.critical_path),
            "warnings": plan.warnings,
        }

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"ProjectPlanner("
            f"project='{self.project_name}', "
            f"tasks={len(self.tasks)}, "
            f"resources={len(self.resources)}, "
            f"deadline={self.deadline})"
        )
