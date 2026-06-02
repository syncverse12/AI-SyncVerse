"""
Domain models — typed Pydantic schemas for every layer of the risk engine.
Single source of truth for data shapes across API, services, and AI.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════════════════════════════
# Enumerations
# ══════════════════════════════════════════════════════════════════════════════

class RiskCategory(str, Enum):
    TECHNICAL = "technical"
    TIMELINE = "timeline"
    BUDGET = "budget"
    HUMAN = "human"
    DELIVERY = "delivery"
    CLIENT = "client"
    INFRASTRUCTURE = "infrastructure"


class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


# ══════════════════════════════════════════════════════════════════════════════
# Pre-Project Analysis Input
# ══════════════════════════════════════════════════════════════════════════════

class TeamMember(BaseModel):
    name: str
    role: str
    skills: list[str]
    current_workload_pct: float = Field(ge=0, le=100)
    seniority_years: float = Field(ge=0)


class TechStack(BaseModel):
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    infrastructure: list[str] = Field(default_factory=list)
    third_party_apis: list[str] = Field(default_factory=list)


class ProjectRequirements(BaseModel):
    project_id: UUID = Field(default_factory=uuid4)
    project_name: str
    description: str
    client_name: str

    # Schedule
    start_date: datetime
    deadline: datetime
    estimated_hours: float = Field(gt=0)

    # Resources
    budget_usd: float = Field(gt=0)
    team: list[TeamMember]

    # Technical
    tech_stack: TechStack
    required_skills: list[str] = Field(default_factory=list)
    has_clear_requirements: bool = True
    requirement_completeness_pct: float = Field(default=80, ge=0, le=100)

    # Context
    similar_past_projects: list[str] = Field(default_factory=list)
    dependencies_count: int = Field(default=0, ge=0)
    third_party_integrations_count: int = Field(default=0, ge=0)
    infrastructure_ready: bool = True
    client_responsiveness: float = Field(default=7.0, ge=0, le=10)

    @field_validator("deadline")
    @classmethod
    def deadline_after_start(cls, v: datetime, info: Any) -> datetime:
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("deadline must be after start_date")
        return v


# ══════════════════════════════════════════════════════════════════════════════
# Live Monitoring Input
# ══════════════════════════════════════════════════════════════════════════════

class LiveProjectMetrics(BaseModel):
    project_id: UUID
    snapshot_at: datetime = Field(default_factory=datetime.utcnow)

    # Sprint / velocity
    sprint_velocity: float             # story points per sprint
    planned_velocity: float
    sprint_completion_rate: float = Field(ge=0, le=1)

    # Task health
    overdue_tasks: int = Field(ge=0)
    total_tasks: int = Field(ge=0)
    blocked_tasks: int = Field(ge=0)
    task_reassignment_count: int = Field(default=0, ge=0)

    # Activity
    github_commits_last_7d: int = Field(default=0, ge=0)
    pr_open_count: int = Field(default=0, ge=0)
    pr_avg_review_hours: float = Field(default=0.0, ge=0)

    # QA & Deployment
    deployment_failures_last_30d: int = Field(default=0, ge=0)
    qa_failure_rate: float = Field(default=0.0, ge=0, le=1)

    # Human
    team_overtime_hours_avg: float = Field(default=0.0, ge=0)
    team_absences_count: int = Field(default=0, ge=0)
    negative_sentiment_score: float = Field(default=0.0, ge=0, le=1)

    # Client
    client_alignment_score: float = Field(default=8.0, ge=0, le=10)
    client_response_delay_hours: float = Field(default=0.0, ge=0)
    unresolved_client_feedback: int = Field(default=0, ge=0)


# ══════════════════════════════════════════════════════════════════════════════
# Risk Scoring
# ══════════════════════════════════════════════════════════════════════════════

class CategoryRiskScore(BaseModel):
    category: RiskCategory
    score: float = Field(ge=0, le=1)
    severity: RiskSeverity
    contributing_factors: list[str]
    weight: float = Field(ge=0, le=1)


class RiskScoreBreakdown(BaseModel):
    overall: float = Field(ge=0, le=1)
    severity: RiskSeverity
    categories: list[CategoryRiskScore]
    confidence: float = Field(ge=0, le=1, description="Model confidence in this score")


# ══════════════════════════════════════════════════════════════════════════════
# AI Risk Report
# ══════════════════════════════════════════════════════════════════════════════

class MitigationAction(BaseModel):
    priority: int = Field(ge=1, le=5, description="1 = highest priority")
    action: str
    owner_role: str
    estimated_impact: str
    timeframe_days: int


class HistoricalSimilarCase(BaseModel):
    project_name: str
    similarity_score: float = Field(ge=0, le=1)
    outcome: str
    key_lesson: str


class RiskReport(BaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    report_type: str  # "pre_project" | "live_update"

    # Core scores
    scores: RiskScoreBreakdown

    # Probabilities
    delay_probability: float = Field(ge=0, le=1)
    budget_overrun_probability: float = Field(ge=0, le=1)
    delivery_confidence: float = Field(ge=0, le=1)
    burnout_probability: float = Field(ge=0, le=1)

    # AI Reasoning
    executive_summary: str
    root_causes: list[str]
    predicted_consequences: list[str]
    mitigation_plan: list[MitigationAction]

    # Historical context
    similar_historical_cases: list[HistoricalSimilarCase]

    # ML metadata
    ml_model_version: str = "1.0.0"


# ══════════════════════════════════════════════════════════════════════════════
# Alerts
# ══════════════════════════════════════════════════════════════════════════════

class AlertPayload(BaseModel):
    alert_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    fired_at: datetime = Field(default_factory=datetime.utcnow)

    severity: RiskSeverity
    risk_category: RiskCategory
    status: AlertStatus = AlertStatus.ACTIVE

    # Content
    title: str
    message: str
    root_cause: str
    ai_insight: str
    recommended_action: str

    # Metrics
    previous_risk_score: float = Field(ge=0, le=1)
    current_risk_score: float = Field(ge=0, le=1)
    delta: float

    # Routing
    escalation_level: int = Field(default=1, ge=1, le=3)
    notify_roles: list[str] = Field(default_factory=list)

    @field_validator("delta", mode="before")
    @classmethod
    def compute_delta(cls, v: Any, info: Any) -> float:
        if v is None and "current_risk_score" in info.data and "previous_risk_score" in info.data:
            return round(info.data["current_risk_score"] - info.data["previous_risk_score"], 4)
        return v


class AlertAcknowledgeRequest(BaseModel):
    alert_id: UUID
    acknowledged_by: str
    note: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# API Responses
# ══════════════════════════════════════════════════════════════════════════════

class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Any | None = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    has_more: bool


class WebSocketMessage(BaseModel):
    event: str
    project_id: UUID
    payload: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)
