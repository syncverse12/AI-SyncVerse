"""
app/models/schemas.py
---------------------
Pydantic v2 request and response schemas for the FastAPI layer.
Kept completely separate from the engine's dataclasses in planner/models.py.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_EVENTS = {
    "task_completed_early",
    "task_completed_late",
    "task_added",
    "task_removed",
    "resource_unavailable",
    "resource_capacity_changed",
    "dependency_changed",
}


# ── Request schemas ───────────────────────────────────────────────────────────

class ResourceIn(BaseModel):
    id: Optional[str] = Field(default=None, examples=["r-001"])
    name: str = Field(..., min_length=1, examples=["Alice Chen"])
    capacity: float = Field(default=1.0, ge=0.0, le=1.0, examples=[1.0])
    skills: List[str] = Field(default_factory=list, examples=[["backend", "python"]])
    available_from: Optional[date] = Field(default=None, examples=["2025-06-02"])
    available_until: Optional[date] = Field(default=None)

    @field_validator("capacity")
    @classmethod
    def capacity_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("capacity must be between 0.0 and 1.0")
        return v


class TaskIn(BaseModel):
    id: Optional[str] = Field(default=None, examples=["t-001"])
    name: str = Field(..., min_length=1, examples=["Design System Architecture"])
    description: str = Field(default="")
    estimated_hours: Optional[float] = Field(
        default=None, ge=0.0,
        description="Omit to let the AI estimator fill it in.",
        examples=[16.0],
    )
    priority: str = Field(default="medium", examples=["high"])
    required_skills: List[str] = Field(default_factory=list, examples=[["backend"]])
    dependencies: List[str] = Field(default_factory=list, examples=[["t-001"]])
    is_milestone: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("priority")
    @classmethod
    def priority_valid(cls, v: str) -> str:
        if v not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(VALID_PRIORITIES)}")
        return v


class ProjectRequest(BaseModel):
    """Body for POST /plan."""
    project_name: str = Field(..., min_length=1, examples=["SaaS MVP"])
    deadline: date = Field(..., examples=["2025-09-01"])
    project_start: Optional[date] = Field(default=None, examples=["2025-06-02"])
    sprint_length_days: int = Field(default=14, ge=1, le=90)
    hours_per_day: float = Field(default=8.0, ge=1.0, le=24.0)
    tasks: List[TaskIn] = Field(..., min_length=1)
    resources: List[ResourceIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def deadline_after_start(self) -> "ProjectRequest":
        start = self.project_start or date.today()
        if self.deadline <= start:
            raise ValueError("deadline must be after project_start")
        return self


class ReplanEventRequest(BaseModel):
    """
    Body for POST /plan/{project_id}/replan.

    new_value type per event_type
    ─────────────────────────────────────────────
    task_completed_early / late  → float (actual hours)
    resource_capacity_changed    → float (0.0–1.0)
    task_added                   → dict matching TaskIn
    dependency_changed           → list[str] (task IDs)
    task_removed / unavailable   → omit
    """
    event_type: str = Field(..., examples=["task_completed_late"])
    task_id: Optional[str] = Field(default=None, examples=["t-003"])
    resource_id: Optional[str] = Field(default=None, examples=["r-001"])
    new_value: Optional[Any] = Field(default=None, examples=[64.0])

    @field_validator("event_type")
    @classmethod
    def event_type_valid(cls, v: str) -> str:
        if v not in VALID_EVENTS:
            raise ValueError(f"event_type must be one of {sorted(VALID_EVENTS)}")
        return v


# ── Response schemas ──────────────────────────────────────────────────────────

class TaskOut(BaseModel):
    id: str
    name: str
    description: str
    estimated_hours: Optional[float]
    actual_hours: float
    dependencies: List[str]
    assigned_to: Optional[str]
    status: str
    priority: str
    required_skills: List[str]
    start_date: Optional[str]
    end_date: Optional[str]
    sprint_id: Optional[int]
    is_milestone: bool
    duration_days: Optional[float]
    metadata: Dict[str, Any]


class SprintOut(BaseModel):
    id: int
    start_date: str
    end_date: str
    task_ids: List[str]
    capacity_hours: float
    planned_hours: float
    utilisation: float
    duration_days: int


class ResourceOut(BaseModel):
    id: str
    name: str
    capacity: float
    skills: List[str]
    available_from: str
    available_until: Optional[str]


class PlanResponse(BaseModel):
    project_id: str
    project_name: str
    deadline: str
    created_at: str
    is_on_time: bool
    completion_date: Optional[str]
    total_estimated_hours: float
    critical_path: List[str]
    warnings: List[str]
    tasks: List[TaskOut]
    sprints: List[SprintOut]
    resources: List[ResourceOut]


class ReplanResponse(BaseModel):
    project_id: str
    event_type: str
    project_name: str
    deadline: str
    created_at: str
    is_on_time: bool
    completion_date: Optional[str]
    total_estimated_hours: float
    critical_path: List[str]
    warnings: List[str]
    tasks: List[TaskOut]
    sprints: List[SprintOut]
    resources: List[ResourceOut]


class SummaryResponse(BaseModel):
    project_id: str
    project_name: str
    deadline: str
    is_on_time: bool
    completion_date: Optional[str]
    total_tasks: int
    total_sprints: int
    total_resources: int
    critical_path_length: int
    warnings: List[str]


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: str
