"""
Output contract of the whole service. This is the ONLY thing the FastAPI
router returns — it's assembled exclusively by the Report Builder, never
directly by the LLM or the Risk Engine.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

Source = Literal["calculated", "ai_estimated"]
Severity = Literal["Low", "Medium", "High", "Critical"]
Priority = Literal["Low", "Medium", "High", "Critical"]


class CalculatedMetric(BaseModel):
    name: str
    value: str
    source: Source = "calculated"


class AIEstimatedMetric(BaseModel):
    name: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    source: Source = "ai_estimated"


class RiskCategory(BaseModel):
    name: str
    score: float = Field(ge=0, le=100)
    severity: Severity
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: Source
    used_metrics: List[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    priority: Priority
    related_risk: str
    action: str


class ReportMetadata(BaseModel):
    generated_at: datetime
    project_id: str
    analysis_version: str
    model: str
    execution_time_ms: float
    data_completeness: float
    collection_mode: str
    missing_sources: List[str] = Field(default_factory=list)


class OverallRisk(BaseModel):
    score: float = Field(ge=0, le=100)
    level: Severity
    confidence: float = Field(ge=0.0, le=1.0)


class RiskReport(BaseModel):
    overall_risk: OverallRisk
    risk_categories: List[RiskCategory]
    calculated_metrics: List[CalculatedMetric]
    ai_estimated_metrics: List[AIEstimatedMetric]
    recommendations: List[Recommendation]
    metadata: ReportMetadata
