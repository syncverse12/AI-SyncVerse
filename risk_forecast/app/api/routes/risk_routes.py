"""
Risk Intelligence API — all endpoints for the risk engine.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_redis
from app.core.logging import get_logger
from app.models.schemas import (
    AlertAcknowledgeRequest,
    LiveProjectMetrics,
    ProjectRequirements,
    RiskReport,
    SuccessResponse,
)
from app.realtime.ws_manager import handle_ws_connection
from app.services.dependencies import get_risk_service, get_alert_repository

logger = get_logger(__name__)

router = APIRouter(prefix="/risk", tags=["Risk Intelligence"])


# ── Pre-Project Analysis ──────────────────────────────────────────────────────

@router.post(
    "/analyze-project",
    response_model=RiskReport,
    status_code=status.HTTP_201_CREATED,
    summary="Pre-project risk forecast",
    description=(
        "Run a comprehensive pre-project risk analysis. "
        "Combines rule-based scoring, ML predictions, RAG historical context, "
        "and LLM reasoning to produce a structured risk report."
    ),
)
async def analyze_project(
    requirements: ProjectRequirements,
    risk_service=Depends(get_risk_service),
) -> RiskReport:
    try:
        return await risk_service.analyze_pre_project(requirements)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Pre-project analysis failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Analysis failed — see logs")


# ── Live Update ───────────────────────────────────────────────────────────────

@router.post(
    "/live-update",
    response_model=RiskReport,
    summary="Live risk update from real-time metrics",
    description=(
        "Push a live metrics snapshot to update the project's risk score. "
        "Triggers alert evaluation and broadcasts to WebSocket subscribers."
    ),
)
async def live_update(
    metrics: LiveProjectMetrics,
    risk_service=Depends(get_risk_service),
) -> RiskReport:
    try:
        return await risk_service.update_live_risk(metrics)
    except Exception as exc:
        logger.error("Live update failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Live update failed")


# ── Project Risk Report ───────────────────────────────────────────────────────

@router.get(
    "/project/{project_id}",
    response_model=RiskReport,
    summary="Get latest risk report for a project",
)
async def get_project_risk(
    project_id: UUID,
    risk_service=Depends(get_risk_service),
) -> RiskReport:
    snapshot = await risk_service.get_project_snapshot(project_id)
    if snapshot.get("status") == "no_data":
        raise HTTPException(
            status_code=404,
            detail=f"No risk report found for project {project_id}",
        )
    return snapshot


# ── History / Timeline ────────────────────────────────────────────────────────

@router.get(
    "/history/{project_id}",
    response_model=list[dict],
    summary="Risk score timeline for dashboard charts",
)
async def get_risk_history(
    project_id: UUID,
    limit: int = Query(default=30, ge=1, le=365),
    risk_service=Depends(get_risk_service),
) -> list[dict]:
    return await risk_service.get_risk_history(project_id, limit=limit)


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get(
    "/alerts",
    summary="List active risk alerts",
)
async def get_alerts(
    project_id: UUID | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    alert_repo=Depends(get_alert_repository),
) -> list[dict]:
    return await alert_repo.list_alerts(
        project_id=project_id,
        severity=severity,
        limit=limit,
    )


@router.post(
    "/alerts/acknowledge",
    response_model=SuccessResponse,
    summary="Acknowledge a risk alert",
)
async def acknowledge_alert(
    req: AlertAcknowledgeRequest,
    alert_repo=Depends(get_alert_repository),
) -> SuccessResponse:
    updated = await alert_repo.acknowledge(req.alert_id, req.acknowledged_by, req.note)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    return SuccessResponse(message=f"Alert {req.alert_id} acknowledged")


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/{project_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    project_id: str,
    risk_service=Depends(get_risk_service),
) -> None:
    """
    WebSocket endpoint for realtime risk updates.

    Events emitted:
      - snapshot:    Initial risk state on connect
      - risk_update: New risk scores computed
      - alert:       Alert fired for this project
      - heartbeat:   Keep-alive ping every 30s
    """
    await handle_ws_connection(websocket, project_id, risk_service)
