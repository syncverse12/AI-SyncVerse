"""
models.py
---------
Core domain models: Task, Resource, Sprint, ProjectPlan, ReplanningEvent.
All classes are plain Python dataclasses with a .to_dict() method so they
serialise cleanly to JSON without any FastAPI/Pydantic coupling.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Enumerations ────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    BLOCKED     = "blocked"
    CANCELLED   = "cancelled"


class TaskPriority(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class EventType(str, Enum):
    TASK_COMPLETED_EARLY      = "task_completed_early"
    TASK_COMPLETED_LATE       = "task_completed_late"
    TASK_ADDED                = "task_added"
    TASK_REMOVED              = "task_removed"
    RESOURCE_UNAVAILABLE      = "resource_unavailable"
    RESOURCE_CAPACITY_CHANGED = "resource_capacity_changed"
    DEPENDENCY_CHANGED        = "dependency_changed"


# ── Resource ────────────────────────────────────────────────────────────────

@dataclass
class Resource:
    name: str
    capacity: float = 1.0
    skills: List[str] = field(default_factory=list)
    available_from: date = field(default_factory=date.today)
    available_until: Optional[date] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

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
            "available_until": self.available_until.isoformat() if self.available_until else None,
        }


# ── Task ────────────────────────────────────────────────────────────────────

@dataclass
class Task:
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
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_days(self) -> Optional[float]:
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


# ── Sprint ───────────────────────────────────────────────────────────────────

@dataclass
class Sprint:
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


# ── ProjectPlan ───────────────────────────────────────────────────────────────

@dataclass
class ProjectPlan:
    project_name: str
    deadline: date
    tasks: List[Task] = field(default_factory=list)
    sprints: List[Sprint] = field(default_factory=list)
    resources: List[Resource] = field(default_factory=list)
    critical_path: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    warnings: List[str] = field(default_factory=list)

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
            "completion_date": self.completion_date.isoformat() if self.completion_date else None,
            "total_estimated_hours": self.total_estimated_hours,
            "critical_path": self.critical_path,
            "warnings": self.warnings,
            "tasks": [t.to_dict() for t in self.tasks],
            "sprints": [s.to_dict() for s in self.sprints],
            "resources": [r.to_dict() for r in self.resources],
        }


# ── ReplanningEvent ───────────────────────────────────────────────────────────

@dataclass
class ReplanningEvent:
    event_type: EventType
    task_id: Optional[str] = None
    resource_id: Optional[str] = None
    new_value: Optional[Any] = None
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        return {
            "event_type": self.event_type.value,
            "task_id": self.task_id,
            "resource_id": self.resource_id,
            "occurred_at": self.occurred_at.isoformat(),
        }
