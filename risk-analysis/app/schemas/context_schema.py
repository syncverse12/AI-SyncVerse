"""
Normalized data contract produced by the Data Collector layer.

This is the ONLY shape the Metrics Engine is allowed to depend on. Whether
the data came from the unified /risk-context endpoint (Mode 1) or was
assembled from several individual endpoints (Mode 2), it must be mapped into
this schema before leaving the Data Collector. That's what keeps the rest of
the pipeline agnostic to which mode fetched the data.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"
    blocked = "blocked"


class RiskSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ProjectInfo(BaseModel):
    project_id: str
    project_name: str
    budget: Optional[float] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class TaskItem(BaseModel):
    task_id: str
    title: str
    status: TaskStatus
    priority: Optional[str] = None
    created_at: Optional[datetime] = None
    assigned_user_id: Optional[str] = None
    depends_on_task_ids: List[str] = Field(default_factory=list)


class TimelineItem(BaseModel):
    timeline_id: str
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    estimated_time: Optional[float] = None
    status: Optional[str] = None


class MilestoneItem(BaseModel):
    milestone_id: str
    name: str
    target_date: Optional[datetime] = None
    status: Optional[str] = None


class ConfirmedRiskItem(BaseModel):
    """Maps directly to the existing `Risks` table — ground truth, not inferred."""
    risk_id: str
    risk_name: str
    severity: RiskSeverity
    status: Optional[str] = None
    date_identified: Optional[datetime] = None


class TimeLogItem(BaseModel):
    time_id: str
    task_id: str
    user_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[float] = None


class TeamMemberItem(BaseModel):
    user_id: str
    task_capacity: Optional[float] = None
    assigned_task_count: int = 0


class MeetingItem(BaseModel):
    meeting_id: str
    start_time: Optional[datetime] = None


class ProjectContext(BaseModel):
    """
    The full normalized payload handed to the Metrics Engine.

    `missing_sources` and `data_completeness` are populated by the Data
    Collector (never by the caller) so downstream layers know exactly which
    parts of this object are trustworthy versus empty-because-unavailable.
    """

    project: ProjectInfo
    tasks: List[TaskItem] = Field(default_factory=list)
    timeline: List[TimelineItem] = Field(default_factory=list)
    milestones: List[MilestoneItem] = Field(default_factory=list)
    confirmed_risks: List[ConfirmedRiskItem] = Field(default_factory=list)
    time_logs: List[TimeLogItem] = Field(default_factory=list)
    team_members: List[TeamMemberItem] = Field(default_factory=list)
    meetings: List[MeetingItem] = Field(default_factory=list)

    collection_mode: str = Field(description="'unified' or 'multi_endpoint'")
    missing_sources: List[str] = Field(default_factory=list)
    data_completeness: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Fraction of expected sources successfully collected"
    )
