"""
context/builder.py
-------------------
        Data Provider
                |
        Context Builder   <-- you are here
                |
        Metrics Engine

Transforms a RawTeamSnapshot (provider-shaped) into a WorkloadContext
(business-shaped). Everything after this point is provider-agnostic.

Deterministic-only at this stage: task complexity and availability score
are seeded with safe, explainable heuristics (not the LLM) so the pipeline
is fully usable even if AI Enrichment is skipped or fails. The AI
Enrichment layer later *refines* these same fields in place.
"""

from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from app.config import get_settings
from app.core.exceptions import ContextBuildError
from app.core.logging import get_logger
from app.models.context import WorkloadContext
from app.models.raw import RawTask, RawTeamSnapshot, ACTIVE_TASK_STATUSES
from app.models.schemas import (
    ComplexityLevel, Employee, Task, TaskComplexityDistribution,
)

logger = get_logger(__name__)


class ContextBuilder:
    def __init__(self) -> None:
        self._settings = get_settings()

    def build(self, snapshot: RawTeamSnapshot, source: str = "unknown") -> WorkloadContext:
        try:
            return self._build(snapshot, source)
        except Exception as exc:  # noqa: BLE001 — intentionally broad, wrapped below
            raise ContextBuildError(f"Failed to build context for {snapshot.scope_id}: {exc}") from exc

    # ------------------------------------------------------------------

    def _build(self, snapshot: RawTeamSnapshot, source: str) -> WorkloadContext:
        tasks_by_user: Dict[str, List[RawTask]] = defaultdict(list)
        for t in snapshot.tasks:
            if t.assigned_to_user_id:
                tasks_by_user[t.assigned_to_user_id].append(t)

        minutes_by_user: Dict[str, int] = defaultdict(int)
        for log in snapshot.time_logs:
            minutes_by_user[log.user_id] += log.duration_minutes

        employees: List[Employee] = []
        tasks: List[Task] = []
        warnings = list(snapshot.data_quality_warnings)

        for raw_emp in snapshot.employees:
            emp_tasks = tasks_by_user.get(raw_emp.id, [])
            active = [t for t in emp_tasks if t.is_active]
            delayed = [t for t in active if t.is_overdue]

            complexity_dist = self._heuristic_complexity_distribution(active)
            availability = self._heuristic_availability_score(
                raw_emp.availability_status, len(active), minutes_by_user.get(raw_emp.id, 0)
            )
            success_rate = self._completion_success_rate(emp_tasks)

            employees.append(
                Employee(
                    id=_stable_int_id(raw_emp.id),
                    name=raw_emp.full_name,
                    active_tasks=len(active),
                    delayed_tasks=len(delayed),
                    availability_score=availability,
                    task_complexity_distribution=complexity_dist,
                    past_success_rate=success_rate,
                    skills=raw_emp.skills,
                    role=raw_emp.role or "engineer",
                )
            )

            for t in emp_tasks:
                tasks.append(
                    Task(
                        id=_stable_int_id(t.id),
                        title=t.title,
                        complexity=self._task_complexity_heuristic(t),
                        priority=t.priority,
                        assigned_to=_stable_int_id(raw_emp.id),
                        is_delayed=t.is_overdue,
                        estimated_hours=max(0.5, minutes_by_user.get(raw_emp.id, 0) / 60 / max(1, len(emp_tasks))),
                        tags=[t.category_name] if t.category_name else [],
                    )
                )

        if not employees:
            warnings.append("No employees resolved for this scope.")

        raw_tasks_by_employee = {raw.id: tasks_by_user.get(raw.id, []) for raw in snapshot.employees}

        logger.info(
            "Context built",
            extra={"scope_id": snapshot.scope_id, "employees": len(employees), "tasks": len(tasks)},
        )

        return WorkloadContext(
            scope_type=snapshot.scope_type,
            scope_id=snapshot.scope_id,
            scope_name=snapshot.scope_name,
            source=source,
            employees=employees,
            tasks=tasks,
            raw_tasks_by_employee=raw_tasks_by_employee,
            data_quality_warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Deterministic heuristics (interim — refined by AI Enrichment layer)
    # ------------------------------------------------------------------

    def _task_complexity_heuristic(self, t: RawTask) -> ComplexityLevel:
        """Priority is the only numeric signal available pre-AI; used only
        as a seed value. AI Enrichment overwrites this using task titles/
        descriptions/category once it runs."""
        if t.priority >= 9:
            return ComplexityLevel.CRITICAL
        if t.priority >= 7:
            return ComplexityLevel.HIGH
        if t.priority >= 4:
            return ComplexityLevel.MEDIUM
        return ComplexityLevel.LOW

    def _heuristic_complexity_distribution(self, active_tasks: List[RawTask]) -> TaskComplexityDistribution:
        dist = TaskComplexityDistribution()
        for t in active_tasks:
            level = self._task_complexity_heuristic(t)
            setattr(dist, level.value, getattr(dist, level.value) + 1)
        return dist

    def _heuristic_availability_score(self, status_text: str | None, active_count: int, logged_minutes: int) -> float:
        """Deterministic seed for availability (0-100). AI Enrichment
        reconciles this with the free-text UserSettings.AvailabilityStatus."""
        text = (status_text or "").strip().lower()
        text_bias = {"available": 70.0, "free": 80.0, "busy": 25.0, "away": 10.0, "offline": 5.0}.get(text, 50.0)
        capacity_hours = self._settings.STANDARD_CAPACITY_HOURS_PER_DAY * self._settings.CAPACITY_LOOKBACK_DAYS
        used_hours = logged_minutes / 60
        capacity_bias = max(0.0, min(100.0, 100.0 - (used_hours / max(capacity_hours, 1)) * 100))
        load_bias = max(0.0, 100.0 - active_count * 12.0)
        return round((text_bias + capacity_bias + load_bias) / 3, 1)

    def _completion_success_rate(self, tasks: List[RawTask]) -> float:
        terminal = [t for t in tasks if t.status.value in ("done", "cancelled")]
        if not terminal:
            return 0.85  # neutral default, matches original schema default
        done = [t for t in terminal if t.status.value == "done"]
        return round(len(done) / len(terminal), 2)


def _stable_int_id(external_id: str) -> int:
    """Employee/Task schemas use int ids (legacy contract). Backend/demo ids
    are strings (GUIDs), so we map deterministically to a positive int for
    internal use while the original string id is preserved via raw_tasks_by_employee
    / RawTeamSnapshot for anything that needs it."""
    return abs(hash(external_id)) % 2_147_483_647
