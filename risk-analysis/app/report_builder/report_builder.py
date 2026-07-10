"""
Assembles the final RiskReport JSON. This is the ONLY place that constructs
a RiskReport — the LLM never formats the final output, and the Risk Engine
never adds metadata. Single responsibility: merge + order + package.
"""

from datetime import datetime, timezone
from typing import List
from app.core.config import get_settings
from app.schemas.context_schema import ProjectContext
from app.schemas.report_schema import (
    RiskReport, RiskCategory, CalculatedMetric, AIEstimatedMetric,
    Recommendation, OverallRisk, ReportMetadata,
)

PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def build_report(
    context: ProjectContext,
    overall_risk: OverallRisk,
    risk_categories: List[RiskCategory],
    calculated_metrics: List[CalculatedMetric],
    ai_estimated_metrics: List[AIEstimatedMetric],
    recommendations: List[Recommendation],
    execution_time_ms: float,
    model_used: str,
) -> RiskReport:
    settings = get_settings()

    sorted_recommendations = sorted(
        recommendations, key=lambda r: PRIORITY_ORDER.get(r.priority, 4)
    )

    metadata = ReportMetadata(
        generated_at=datetime.now(timezone.utc),
        project_id=context.project.project_id,
        analysis_version=settings.analysis_version,
        model=model_used,
        execution_time_ms=execution_time_ms,
        data_completeness=context.data_completeness,
        collection_mode=context.collection_mode,
        missing_sources=context.missing_sources,
    )

    return RiskReport(
        overall_risk=overall_risk,
        risk_categories=risk_categories,
        calculated_metrics=calculated_metrics,
        ai_estimated_metrics=ai_estimated_metrics,
        recommendations=sorted_recommendations,
        metadata=metadata,
    )
