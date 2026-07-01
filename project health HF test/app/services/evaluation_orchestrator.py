"""
app/services/evaluation_orchestrator.py
Ties together all three evaluation layers + drift + risk prediction.
This is the single entry-point called by routers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.logging import get_logger
from app.models.domain import (
    AIJudgeResult,
    AlignmentScoreResult,
    HealthScoreResult,
    Project,
)
from app.services.ai_judge_service import run_ai_judge
from app.services.alignment_service import compute_alignment_score
from app.services.drift_service import DriftReport, RiskForecast, detect_drift, predict_risk
from app.services.health_service import compute_health_score
from app.services.rag_service import build_rag_context

logger = get_logger(__name__)


@dataclass
class FullEvaluation:
    health: HealthScoreResult
    alignment: AlignmentScoreResult
    ai_judge: AIJudgeResult
    drift: DriftReport
    forecast: RiskForecast


async def evaluate_project(
    project: Project,
    run_judge: bool = True,
    run_critic: bool = True,
    forecast_days: int = 14,
) -> FullEvaluation:
    """
    Full pipeline:
    1. Compute Health Score
    2. Compute Alignment Score
    3. Build semantic context
    4. Run AI Judge (with optional critic loop)
    5. Detect drift
    6. Predict risk
    """

    # Step 1 — Health Score (pure computation, no I/O)
    health = compute_health_score(project)

    # Step 2 — Alignment Score
    alignment = await compute_alignment_score(project)

    # Step 3 — RAG context assembly
    rag_ctx = await build_rag_context(project, health, alignment)

    # Step 4 — AI Judge
    if run_judge:
        ai_judge = await run_ai_judge(project, rag_ctx, run_critic=run_critic)
    else:
        # Return a placeholder when judge is disabled (e.g. in tests)
        from app.models.domain import RiskLevel
        ai_judge = AIJudgeResult(
            project_id=project.id,
            ai_judge_score=0.0,
            confidence=0.0,
            adjusted_health_score=health.health_score,
            risk_level=RiskLevel.LOW,
            summary="AI Judge skipped.",
            key_issues=[],
            recommendations=[],
            detected_gaps=[],
        )

    # Step 5 — Drift detection
    drift = detect_drift(project, alignment)

    # Step 6 — Risk forecast
    forecast = predict_risk(project, health, alignment, forecast_days=forecast_days)

    logger.info(
        "evaluation_complete",
        project_id=project.id,
        health=health.health_score,
        alignment=alignment.alignment_score,
        judge_score=ai_judge.ai_judge_score,
        risk=forecast.overall_risk,
    )
    return FullEvaluation(
        health=health,
        alignment=alignment,
        ai_judge=ai_judge,
        drift=drift,
        forecast=forecast,
    )
