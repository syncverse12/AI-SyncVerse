"""
models/ai_models.py
--------------------
Shape shared by every AI-estimated metric anywhere in the system:

    {"value": ..., "source": "ai_estimated", "confidence": 0.84, "reason": "..."}

Deterministic values never use this wrapper — only genuinely inferred ones.
"""

from __future__ import annotations
from typing import Generic, Literal, TypeVar, Union
from pydantic import BaseModel, Field

T = TypeVar("T")


class AIEstimatedValue(BaseModel, Generic[T]):
    value: T
    source: Literal["ai_estimated"] = "ai_estimated"
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class DeterministicValue(BaseModel, Generic[T]):
    """Optional symmetric wrapper for deterministic values when the Report
    Builder needs to distinguish provenance explicitly in the API response."""
    value: T
    source: Literal["deterministic"] = "deterministic"


AnyMetricValue = Union[AIEstimatedValue, DeterministicValue]


class EmployeeAIEnrichment(BaseModel):
    """All AI-estimated metrics for a single employee, produced in ONE
    batched LLM call per analysis run (never one call per metric)."""
    estimated_task_difficulty: AIEstimatedValue[str]
    estimated_work_complexity: AIEstimatedValue[str]
    burnout_indicator: AIEstimatedValue[str]
    productivity_trend: AIEstimatedValue[str]
    focus_capacity: AIEstimatedValue[str]
    context_switching_cost: AIEstimatedValue[str]
    collaboration_difficulty: AIEstimatedValue[str]
    estimated_priority_weight: AIEstimatedValue[float]
    availability_score: AIEstimatedValue[float]
    narrative: str = ""  # short human-readable explanation for this employee


class TaskComplexityEstimate(BaseModel):
    task_id: str
    complexity: AIEstimatedValue[str]  # "low" | "medium" | "high" | "critical"
