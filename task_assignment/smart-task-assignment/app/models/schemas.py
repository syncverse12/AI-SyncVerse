from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class SeniorityLevel(str, Enum):
    JUNIOR = "Junior"
    MID = "Mid"
    SENIOR = "Senior"
    LEAD = "Lead"


class TaskComplexity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


# ─────────────────────────────────────────────
# Employee Models
# ─────────────────────────────────────────────

class Employee(BaseModel):
    id: int
    name: str
    track: str
    skills: List[str]
    level: SeniorityLevel
    active_tasks: int = 0
    availability_score: float = Field(ge=0, le=100, default=100.0)
    past_success_rate: float = Field(ge=0.0, le=1.0, default=0.85)

    class Config:
        use_enum_values = True


class EmployeeCreate(BaseModel):
    name: str
    track: str
    skills: List[str]
    level: SeniorityLevel
    active_tasks: int = 0
    availability_score: float = Field(ge=0, le=100, default=100.0)
    past_success_rate: float = Field(ge=0.0, le=1.0, default=0.85)


class EmployeeStatusUpdate(BaseModel):
    employee_id: int
    active_tasks: Optional[int] = None
    availability_score: Optional[float] = None
    past_success_rate: Optional[float] = None


# ─────────────────────────────────────────────
# Task Models
# ─────────────────────────────────────────────

class TaskInput(BaseModel):
    description: str
    requester: Optional[str] = "System"
    priority: Optional[str] = "Normal"


class TaskRequirements(BaseModel):
    required_track: str
    required_skills: List[str]
    seniority_level: SeniorityLevel
    complexity: TaskComplexity
    summary: str


# ─────────────────────────────────────────────
# Agent Output Models
# ─────────────────────────────────────────────

class AgentUpdate(BaseModel):
    agent: str
    status: AgentStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None


class SkillMatchResult(BaseModel):
    employee_id: int
    employee_name: str
    skill_score: float          # 0–100
    matched_skills: List[str]
    missing_skills: List[str]


class WorkloadScore(BaseModel):
    employee_id: int
    employee_name: str
    workload_score: float       # 0–100  (higher = more available)


class SeniorityScore(BaseModel):
    employee_id: int
    employee_name: str
    seniority_score: float      # 0–100


class EmployeeRecommendation(BaseModel):
    rank: int
    employee_id: int
    name: str
    track: str
    level: str
    final_score: float
    skill_score: float
    workload_score: float
    seniority_score: float
    performance_score: float
    reason: str
    matched_skills: List[str]


# ─────────────────────────────────────────────
# Pipeline / WebSocket Message Models
# ─────────────────────────────────────────────

class PipelineMessage(BaseModel):
    event: str                              # e.g. "agent_update", "final_result", "error"
    task_id: str
    payload: Dict[str, Any]


class FinalResult(BaseModel):
    task_id: str
    status: str = "complete"
    task_requirements: Optional[TaskRequirements] = None
    updates: List[str]
    final_recommendations: List[EmployeeRecommendation]
