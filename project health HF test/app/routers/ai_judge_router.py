"""
app/routers/ai_judge_router.py
POST /project/{project_id}/ai-judge
POST /project/{project_id}/evaluate  (full pipeline)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from typing import Optional

from app.models.domain import Project
from app.schemas.schemas import AIJudgeResponse, ErrorResponse
from app.services.ai_judge_service import run_ai_judge
from app.services.alignment_service import compute_alignment_score
from app.services.health_service import compute_health_score
from app.services.rag_service import build_rag_context
from app.services.drift_service import detect_drift, predict_risk

router = APIRouter(prefix="/project", tags=["AI Judge"])


class FullEvaluationResponse(BaseModel):
    success: bool = True
    data: dict


@router.post(
    "/{project_id}/ai-judge",
    response_model=AIJudgeResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Run AI Judge Evaluation",
)
async def get_ai_judge(
    project_id: str,
    project: Project = Body(...),
    run_critic: bool = Query(True, description="Enable critic validation loop"),
) -> AIJudgeResponse:
    """
    Layer 3: RAG-grounded LLM evaluation with optional critic loop.
    Uses semantic project context built in memory.
    """
    if project.id != project_id:
        raise HTTPException(status_code=400, detail="project_id mismatch")

    health = compute_health_score(project)
    alignment = await compute_alignment_score(project)
    rag_ctx = await build_rag_context(project, health, alignment)
    result = await run_ai_judge(project, rag_ctx, run_critic=run_critic)
    return AIJudgeResponse(data=result)


@router.post(
    "/{project_id}/evaluate",
    response_model=FullEvaluationResponse,
    summary="Full Pipeline: Health + Alignment + AI Judge + Drift + Forecast",
)
async def full_evaluate(
    project_id: str,
    project: Project = Body(...),
    run_critic: bool = Query(True),
    forecast_days: int = Query(14, ge=1, le=90),
) -> FullEvaluationResponse:
    """
    Single endpoint that runs the complete evaluation pipeline:
    1. Compute project health
    2. Health Score
    3. Alignment Score
    4. AI Judge (with critic)
    5. Drift detection
    6. Predictive risk forecast
    """
    if project.id != project_id:
        raise HTTPException(status_code=400, detail="project_id mismatch")

    health = compute_health_score(project)
    alignment = await compute_alignment_score(project)
    rag_ctx = await build_rag_context(project, health, alignment)
    ai_judge = await run_ai_judge(project, rag_ctx, run_critic=run_critic)
    drift = detect_drift(project, alignment)
    forecast = predict_risk(project, health, alignment, forecast_days=forecast_days)

    return FullEvaluationResponse(data={
        "project_id": project_id,
        "health": health.model_dump(),
        "alignment": alignment.model_dump(),
        "ai_judge": ai_judge.model_dump(),
        "drift": {
            "drift_detected": drift.drift_detected,
            "signals": [
                {
                    "requirement_id": s.requirement_id,
                    "drift_type": s.drift_type,
                    "severity": s.severity,
                    "alignment_score": s.alignment_score,
                }
                for s in drift.signals
            ],
            "summary": drift.summary,
        },
        "forecast": {
            "predicted_misalignment_risk": forecast.predicted_misalignment_risk,
            "predicted_delay_risk": forecast.predicted_delay_risk,
            "predicted_failure_risk": forecast.predicted_failure_risk,
            "overall_risk": forecast.overall_risk,
            "risk_drivers": forecast.risk_drivers,
            "forecast_horizon_days": forecast.forecast_horizon_days,
        },
    })
