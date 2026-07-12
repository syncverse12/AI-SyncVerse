"""
models/raw.py
--------------
Provider-facing models. These mirror the SyncVerse DB shape as exposed by
either the Backend REST API or the Demo JSON fixtures — i.e. they represent
data *before* the Context Builder normalises it. Business logic downstream
of the Context Builder never sees these directly.

Field names follow the DB columns documented in docs/DATABASE_ANALYSIS.md.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Mirrors Tasks.Status (int enum in DB). Exact backend int->name mapping
    is confirmed by the backend team at integration time; values below are
    the conventional SyncVerse lifecycle inferred from column names
    (TaskStartedAt / SubmittedAt / ReviewedAt / TaskCompletedAt)."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"


ACTIVE_TASK_STATUSES = {
    TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.SUBMITTED, TaskStatus.IN_REVIEW
}
TERMINAL_TASK_STATUSES = {TaskStatus.DONE, TaskStatus.CANCELLED}


class RawTask(BaseModel):
    """Mirrors dbo.Tasks — the authoritative task table."""
    id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: int = Field(default=5, ge=1, le=10)
    assigned_to_user_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    reviewed_by_user_id: Optional[str] = None
    due_date: Optional[datetime] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    project_id: Optional[str] = None
    milestone_id: Optional[str] = None
    workspace_id: Optional[str] = None
    task_started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    task_completed_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    depends_on_task_ids: List[str] = Field(default_factory=list)
    comment_count: int = 0

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_TASK_STATUSES

    @property
    def is_overdue(self) -> bool:
        if not (self.due_date and self.is_active):
            return False
        now = datetime.now(self.due_date.tzinfo) if self.due_date.tzinfo else datetime.utcnow()
        return self.due_date < now


class RawTimeLog(BaseModel):
    """Mirrors dbo.TimeLogs."""
    id: str
    task_id: str
    user_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: int = 0


class RawEmployee(BaseModel):
    """Mirrors dbo.AspNetUsers, restricted to workload-relevant columns."""
    id: str
    first_name: str
    last_name: str
    seniority_level: Optional[int] = None
    department: Optional[int] = None
    skills_raw: str = ""  # AspNetUsers.Skills — parsed defensively downstream
    availability_status: Optional[str] = None  # UserSettings.AvailabilityStatus (free text)
    role: Optional[str] = "engineer"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def skills(self) -> List[str]:
        raw = (self.skills_raw or "").strip()
        if not raw:
            return []
        if raw.startswith("["):
            import json
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(s).strip() for s in parsed if str(s).strip()]
            except Exception:
                pass
        return [s.strip() for s in raw.split(",") if s.strip()]


class RawTeamSnapshot(BaseModel):
    """Everything a Data Provider needs to hand off to the Context Builder
    for one analysis scope (a project, a team, or a workspace)."""
    scope_type: str  # "project" | "team" | "workspace"
    scope_id: str
    scope_name: str = ""
    employees: List[RawEmployee] = Field(default_factory=list)
    tasks: List[RawTask] = Field(default_factory=list)
    time_logs: List[RawTimeLog] = Field(default_factory=list)
    data_quality_warnings: List[str] = Field(default_factory=list)
