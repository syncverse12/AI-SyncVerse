"""
models.py
---------
Core domain models for the AI Planning Module.
All classes are Pydantic-compatible dataclasses so they can be
directly serialised / deserialised by FastAPI without any glue code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING    = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED  = "completed"
    BLOCKED    = "blocked"
    CANCELLED  = "cancelled"


class TaskPriority(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    CRITICAL = "critical"


class EventType(str, Enum):
    TASK_COMPLETED_EARLY  = "task_completed_early"
    TASK_COMPLETED_LATE   = "task_completed_late"
    TASK_ADDED            = "task_added"
    TASK_REMOVED          = "task_removed"
    RESOURCE_UNAVAILABLE  = "resource_unavailable"
    RESOURCE_CAPACITY_CHANGED = "resource_capacity_changed"
    DEPENDENCY_CHANGED    = "dependency_changed"


# ---------------------------------------------------------------------------
# Resource
# ---------------------------------------------------------------------------

@dataclass
class Resource:
    """
    Represents a team member / resource that can be assigned tasks.

    Attributes
    ----------
    id              : Unique identifier (auto-generated if omitted).
    name            : Human-readable name.
    capacity        : Daily work capacity expressed as a fraction of a full
                      working day (0.0 – 1.0).  Defaults to 1.0 (full time).
    skills          : Free-form skill tags used for soft matching.
    available_from  : First date on which the resource is available.
    available_until : Last date on which the resource is available
                      (None = no end constraint).
    """
    name: str
    capacity: float = 1.0                        # fraction of a full day
    skills: List[str] = field(default_factory=list)
    available_from: date = field(default_factory=date.today)
    available_until: Optional[date] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # ----- helpers --------------------------------------------------------

    def is_available_on(self, day: date) -> bool:
        if day < self.available_from:
            return False
        if self.available_until and day > self.available_until:
            return False
        return True

    def effective_capacity_on(self, day: date) -> float:
        return self.capacity if self.is_available_on(day) else 0.0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "capacity": self.capacity,
            "skills": self.skills,
            "available_from": self.available_from.isoformat(),
            "available_until": (
                self.available_until.isoformat() if self.available_until else None
            ),
        }


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """
    Represents a single unit of work inside a project.

    Attributes
    ----------
    name             : Human-readable task name.
    id               : Unique identifier (auto-generated if omitted).
    description      : Optional longer description.
    estimated_hours  : Estimated effort in hours.  When None the AI
                       estimation heuristic will fill it in.
    actual_hours     : Hours spent so far (used by the replanning engine).
    dependencies     : IDs of tasks that must complete before this one starts.
    assigned_to      : ID of the Resource this task is assigned to.
    status           : Current lifecycle status.
    priority         : Scheduling priority hint.
    required_skills  : Skill tags required to complete this task.
    start_date       : Scheduled start date (set by the scheduler).
    end_date         : Scheduled end date   (set by the scheduler).
    sprint_id        : Sprint identifier assigned by the sprint generator.
    is_milestone     : Milestone tasks have 0 duration and act as sync points.
    metadata         : Arbitrary key-value store for caller-defined fields.
    """
    name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    estimated_hours: Optional[float] = None
    actual_hours: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    assigned_to: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    required_skills: List[str] = field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    sprint_id: Optional[int] = None
    is_milestone: bool = False
    metadata: Dict = field(default_factory=dict)

    # ----- computed props -------------------------------------------------

    @property
    def duration_days(self) -> Optional[float]:
        """Return scheduled duration in calendar days, or None if unscheduled."""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return None

    @property
    def is_scheduled(self) -> bool:
        return self.start_date is not None and self.end_date is not None

    @property
    def is_complete(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "estimated_hours": self.estimated_hours,
            "actual_hours": self.actual_hours,
            "dependencies": self.dependencies,
            "assigned_to": self.assigned_to,
            "status": self.status.value,
            "priority": self.priority.value,
            "required_skills": self.required_skills,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "sprint_id": self.sprint_id,
            "is_milestone": self.is_milestone,
            "duration_days": self.duration_days,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Sprint
# ---------------------------------------------------------------------------

@dataclass
class Sprint:
    """
    A time-boxed container that groups a set of tasks.

    Attributes
    ----------
    id           : Monotonically increasing sprint number (1-based).
    start_date   : First working day of the sprint.
    end_date     : Last working day of the sprint.
    task_ids     : Ordered list of task IDs included in this sprint.
    capacity_hours : Total available resource hours for the sprint.
    planned_hours  : Sum of estimated hours for all tasks in the sprint.
    """
    id: int
    start_date: date
    end_date: date
    task_ids: List[str] = field(default_factory=list)
    capacity_hours: float = 0.0
    planned_hours: float = 0.0

    @property
    def utilisation(self) -> float:
        if self.capacity_hours == 0:
            return 0.0
        return min(self.planned_hours / self.capacity_hours, 1.0)

    @property
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "task_ids": self.task_ids,
            "capacity_hours": self.capacity_hours,
            "planned_hours": self.planned_hours,
            "utilisation": round(self.utilisation, 3),
            "duration_days": self.duration_days,
        }


# ---------------------------------------------------------------------------
# Project Plan
# ---------------------------------------------------------------------------

@dataclass
class ProjectPlan:
    """
    Top-level container returned by the planner.

    Attributes
    ----------
    project_name    : Human-readable project label.
    deadline        : Hard deadline that the plan must respect.
    tasks           : Complete list of Task objects (scheduled).
    sprints         : Ordered list of Sprint objects.
    resources       : All available resources.
    critical_path   : Ordered list of task IDs on the critical path.
    created_at      : Timestamp when the plan was generated.
    warnings        : Non-fatal issues discovered during planning.
    """
    project_name: str
    deadline: date
    tasks: List[Task] = field(default_factory=list)
    sprints: List[Sprint] = field(default_factory=list)
    resources: List[Resource] = field(default_factory=list)
    critical_path: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    warnings: List[str] = field(default_factory=list)

    # ----- convenience look-ups -------------------------------------------

    def get_task(self, task_id: str) -> Optional[Task]:
        return next((t for t in self.tasks if t.id == task_id), None)

    def get_resource(self, resource_id: str) -> Optional[Resource]:
        return next((r for r in self.resources if r.id == resource_id), None)

    def get_sprint(self, sprint_id: int) -> Optional[Sprint]:
        return next((s for s in self.sprints if s.id == sprint_id), None)

    @property
    def total_estimated_hours(self) -> float:
        return sum(t.estimated_hours or 0.0 for t in self.tasks)

    @property
    def completion_date(self) -> Optional[date]:
        scheduled = [t.end_date for t in self.tasks if t.end_date]
        return max(scheduled) if scheduled else None

    @property
    def is_on_time(self) -> bool:
        cd = self.completion_date
        return cd is not None and cd <= self.deadline

    def to_dict(self) -> Dict:
        return {
            "project_name": self.project_name,
            "deadline": self.deadline.isoformat(),
            "created_at": self.created_at.isoformat(),
            "is_on_time": self.is_on_time,
            "completion_date": (
                self.completion_date.isoformat() if self.completion_date else None
            ),
            "total_estimated_hours": self.total_estimated_hours,
            "critical_path": self.critical_path,
            "warnings": self.warnings,
            "tasks": [t.to_dict() for t in self.tasks],
            "sprints": [s.to_dict() for s in self.sprints],
            "resources": [r.to_dict() for r in self.resources],
        }


# ---------------------------------------------------------------------------
# Replanning Event
# ---------------------------------------------------------------------------

@dataclass
class ReplanningEvent:
    """
    Describes a real-world change that triggers a plan recalculation.

    Attributes
    ----------
    event_type   : The category of change (see EventType enum).
    task_id      : Relevant task ID (when applicable).
    resource_id  : Relevant resource ID (when applicable).
    new_value    : Flexible payload – interpreted differently per event type:
                   - TASK_COMPLETED_EARLY/LATE → actual hours (float)
                   - RESOURCE_CAPACITY_CHANGED  → new capacity 0.0–1.0 (float)
                   - TASK_ADDED                 → Task dataclass instance
                   - DEPENDENCY_CHANGED         → new dependency list (List[str])
    occurred_at  : When the event happened (defaults to now).
    """
    event_type: EventType
    task_id: Optional[str] = None
    resource_id: Optional[str] = None
    new_value: Optional[object] = None
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        return {
            "event_type": self.event_type.value,
            "task_id": self.task_id,
            "resource_id": self.resource_id,
            "occurred_at": self.occurred_at.isoformat(),
        }
