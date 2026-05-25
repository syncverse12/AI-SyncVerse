"""
app/models/domain.py
Core domain models shared across layers.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Enums ───────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VectorDocType(str, Enum):
    REQUIREMENT = "requirement"
    TASK = "task"
    DELIVERABLE = "deliverable"
    NOTE = "note"


# ─── Priority helpers ─────────────────────────────────────────────────────────

PRIORITY_MULTIPLIER: dict[Priority, float] = {
    Priority.CRITICAL: 3.0,
    Priority.HIGH: 2.0,
    Priority.MEDIUM: 1.0,
    Priority.LOW: 0.5,
}


# ─── Input models ────────────────────────────────────────────────────────────

class Goal(BaseModel):
    id: str
    title: str
    weight: float = Field(..., ge=0.0, le=1.0)
    description: Optional[str] = None


class Requirement(BaseModel):
    requirement_id: str
    description: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    project_id: str


class Task(BaseModel):
    id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.MEDIUM
    goal_id: Optional[str] = None
    requirement_id: Optional[str] = None
    deadline: Optional[date] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    output_summary: Optional[str] = None
    project_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    @field_validator("weight", mode="before", check_fields=False)
    @classmethod
    def _default_weight(cls, v):  # pragma: no cover
        return v


class Deliverable(BaseModel):
    id: str
    title: str
    description: str
    task_id: Optional[str] = None
    requirement_id: Optional[str] = None
    project_id: str


class ProjectNote(BaseModel):
    id: str
    content: str
    project_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Project(BaseModel):
    id: str
    name: str
    description: str
    goals: List[Goal] = Field(default_factory=list)
    requirements: List[Requirement] = Field(default_factory=list)
    tasks: List[Task] = Field(default_factory=list)
    deliverables: List[Deliverable] = Field(default_factory=list)
    notes: List[ProjectNote] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Output / scoring models ─────────────────────────────────────────────────

class DelayedTask(BaseModel):
    task_id: str
    title: str
    delay_days: int
    priority: Priority
    delay_contribution: float


class GoalProgressItem(BaseModel):
    goal_id: str
    title: str
    weight: float
    progress: float  # 0–1
    completed_tasks: int
    total_tasks: int


class HealthScoreResult(BaseModel):
    project_id: str
    health_score: float
    completion_rate: float
    goal_progress: float
    efficiency_score: float
    delay_score: float
    delayed_tasks: List[DelayedTask]
    goal_details: List[GoalProgressItem]
    score_breakdown: dict


class RequirementAlignment(BaseModel):
    requirement_id: str
    description: str
    weight: float
    alignment_score: float  # 0–1
    matched_task_ids: List[str]
    alert: Optional[str] = None


class AlignmentAlert(BaseModel):
    level: RiskLevel
    message: str
    affected_ids: List[str]


class AlignmentScoreResult(BaseModel):
    project_id: str
    alignment_score: float  # 0–100
    requirement_details: List[RequirementAlignment]
    alerts: List[AlignmentAlert]
    orphan_task_ids: List[str]


class AIJudgeResult(BaseModel):
    project_id: str
    ai_judge_score: float
    confidence: float
    adjusted_health_score: float
    risk_level: RiskLevel
    summary: str
    key_issues: List[str]
    recommendations: List[str]
    detected_gaps: List[str]
    critic_validated: bool = False
    critic_notes: Optional[str] = None
