"""
Pydantic schemas for the Dynamic Workload Balancing System.
All I/O contracts are defined here for strict validation.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ComplexityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(str, Enum):
    REASSIGN_TASK = "reassign_task"
    SPLIT_TASK = "split_task"
    DELAY_TASK = "delay_task"
    REDISTRIBUTE = "redistribute_workload"
    FLAG_BOTTLENECK = "flag_bottleneck"


class BalanceStatus(str, Enum):
    BALANCED = "balanced"
    IMBALANCE_DETECTED = "imbalance_detected"
    CRITICAL_IMBALANCE = "critical_imbalance"


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class TaskComplexityDistribution(BaseModel):
    low: int = Field(default=0, ge=0, description="Number of low-complexity tasks")
    medium: int = Field(default=0, ge=0, description="Number of medium-complexity tasks")
    high: int = Field(default=0, ge=0, description="Number of high-complexity tasks")
    critical: int = Field(default=0, ge=0, description="Number of critical-complexity tasks")


class Task(BaseModel):
    id: int
    title: str
    complexity: ComplexityLevel = ComplexityLevel.MEDIUM
    priority: int = Field(default=5, ge=1, le=10, description="1=lowest, 10=highest")
    assigned_to: int  # employee id
    is_delayed: bool = False
    estimated_hours: float = Field(default=4.0, ge=0.1)
    tags: List[str] = Field(default_factory=list)


class Employee(BaseModel):
    id: int
    name: str
    active_tasks: int = Field(ge=0)
    task_complexity_distribution: TaskComplexityDistribution = Field(
        default_factory=TaskComplexityDistribution
    )
    delayed_tasks: int = Field(default=0, ge=0)
    availability_score: float = Field(
        ge=0, le=100,
        description="0=fully booked, 100=completely free"
    )
    past_success_rate: float = Field(
        default=0.85, ge=0.0, le=1.0,
        description="Historical task completion success rate"
    )
    skills: List[str] = Field(default_factory=list)
    role: str = "engineer"

    # Populated by the Context Builder when data comes from real/demo
    # providers (never set by the deterministic balancing engine itself).
    ai_enrichment: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_delayed_tasks(self):
        if self.delayed_tasks > self.active_tasks:
            raise ValueError(
                "delayed_tasks cannot exceed active_tasks"
            )
        return self


# ---------------------------------------------------------------------------
# Analysis output models
# ---------------------------------------------------------------------------

class WorkloadMetrics(BaseModel):
    employee_id: int
    employee_name: str
    workload_score: float
    complexity_weight: float
    risk_level: RiskLevel
    risk_score: float          # 0-100 normalised
    reason: str
    is_overloaded: bool
    is_underutilized: bool
    is_bottleneck: bool


class RecommendedAction(BaseModel):
    action: ActionType
    priority: int = Field(ge=1, le=10, description="Urgency of this action")
    from_employee: Optional[str] = None
    to_employee: Optional[str] = None
    task_id: Optional[int] = None
    task_title: Optional[str] = None
    reason: str
    estimated_impact: str       # human-readable impact description
    requires_approval: bool = True   # ALWAYS True — no auto-execution


class BalanceReport(BaseModel):
    status: BalanceStatus
    timestamp: str
    team_health_score: float    # 0-100
    overloaded_employees: List[WorkloadMetrics]
    underutilized_employees: List[WorkloadMetrics]
    bottleneck_employees: List[WorkloadMetrics]
    recommended_actions: List[RecommendedAction]
    summary: str
    metrics: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Real-time event models (WebSocket / SSE)
# ---------------------------------------------------------------------------

class WorkloadEvent(BaseModel):
    event_type: str   # "status_update" | "risk_alert" | "recommendation" | "ping"
    payload: Dict[str, Any]
    timestamp: str


class WorkloadUpdateRequest(BaseModel):
    employees: List[Employee]
    tasks: Optional[List[Task]] = None
    context: Optional[str] = None   # free-text context for LLM reasoning


class WorkloadUpdateResponse(BaseModel):
    report: BalanceReport
    ai_insights: Optional[str] = None   # LLM-generated narrative
