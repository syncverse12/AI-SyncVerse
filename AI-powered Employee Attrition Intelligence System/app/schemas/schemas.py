"""
Pydantic v2 schemas for API request/response validation.
"""

from __future__ import annotations
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ──────────────────────────────────────────────
# Base Schemas
# ──────────────────────────────────────────────

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# ──────────────────────────────────────────────
# Employee Schemas
# ──────────────────────────────────────────────

class EmployeeBase(BaseSchema):
    employee_code: str = Field(..., max_length=50)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=255)
    age: int = Field(..., ge=18, le=70)
    department: str
    job_role: str
    job_level: str
    monthly_income: float = Field(..., gt=0)
    hire_date: date
    years_at_company: float = Field(..., ge=0)
    years_since_last_promotion: float = Field(default=0.0, ge=0)
    years_with_curr_manager: float = Field(default=0.0, ge=0)
    team_id: Optional[str] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeResponse(EmployeeBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ──────────────────────────────────────────────
# Metrics Schemas
# ──────────────────────────────────────────────

class EmployeeMetricsCreate(BaseSchema):
    snapshot_date: date
    performance_rating: float = Field(..., ge=1, le=5)
    job_satisfaction: float = Field(..., ge=1, le=5)
    work_life_balance: float = Field(..., ge=1, le=5)
    environment_satisfaction: float = Field(..., ge=1, le=5)
    overtime_hours: float = Field(default=0.0, ge=0)
    attendance_rate: float = Field(default=1.0, ge=0, le=1)
    workload_score: float = Field(default=5.0, ge=1, le=10)
    team_health_score: float = Field(default=7.0, ge=1, le=10)
    tasks_completed: int = Field(default=0, ge=0)
    tasks_assigned: int = Field(default=0, ge=0)
    missed_deadlines: int = Field(default=0, ge=0)
    overdue_task_ratio: float = Field(default=0.0, ge=0, le=1)
    collaboration_score: Optional[float] = Field(default=7.0, ge=1, le=10)
    leadership_score: Optional[float] = Field(default=None, ge=1, le=10)
    promotion_velocity: Optional[float] = Field(default=None, ge=0)
    training_hours: Optional[float] = Field(default=0.0, ge=0)


# ──────────────────────────────────────────────
# Prediction Response Schemas
# ──────────────────────────────────────────────

class RiskFactor(BaseSchema):
    feature: str
    display_name: str
    impact: float  # positive = increases risk
    direction: str  # "positive_risk" or "negative_risk"
    description: str


class AttritionRecommendation(BaseSchema):
    priority: str  # HIGH, MEDIUM, LOW
    category: str  # compensation, wellbeing, career, management, workload
    action: str
    expected_impact: str


class AttritionPredictionResponse(BaseSchema):
    employee_id: str
    employee_name: Optional[str] = None
    attrition_probability: float = Field(..., ge=0, le=1)
    risk_level: str  # Low, Medium, High
    top_risk_factors: List[RiskFactor]
    recommendations: List[AttritionRecommendation]
    explanation_summary: str
    model_version: Optional[str] = None
    predicted_at: datetime


class PromotionResponse(BaseSchema):
    employee_id: str
    employee_name: Optional[str] = None
    promotion_readiness_score: float = Field(..., ge=0, le=100)
    promotion_recommended: bool
    recommended_role: Optional[str]
    promotion_reasoning: List[str]
    top_strengths: List[str]
    development_areas: List[str]
    predicted_at: datetime


# ──────────────────────────────────────────────
# Team Risk Schemas
# ──────────────────────────────────────────────

class TeamMemberRisk(BaseSchema):
    employee_id: str
    employee_name: str
    job_role: str
    attrition_probability: float
    risk_level: str


class WorkloadDistribution(BaseSchema):
    low: int
    medium: int
    high: int
    overloaded: int


class TeamRiskResponse(BaseSchema):
    team_id: str
    total_employees: int
    average_attrition_probability: float
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    burnout_indicator: str  # Low, Moderate, High, Critical
    average_workload_score: float
    average_team_health: float
    average_work_life_balance: float
    top_risk_employees: List[TeamMemberRisk]
    workload_distribution: WorkloadDistribution
    team_recommendations: List[str]
    analysis_date: datetime


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────

class HealthResponse(BaseSchema):
    status: str
    version: str
    environment: str
    database: str
    redis: str
    ml_models: Dict[str, bool]
    timestamp: datetime


# ──────────────────────────────────────────────
# Generic Responses
# ──────────────────────────────────────────────

class ErrorResponse(BaseSchema):
    code: str
    message: str
    details: Optional[Any] = None


class PaginatedResponse(BaseSchema):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
