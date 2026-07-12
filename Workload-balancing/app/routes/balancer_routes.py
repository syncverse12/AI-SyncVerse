"""
balancer_routes.py
------------------
FastAPI router exposing:

  POST /api/v1/workload/analyze/{scope_type}/{scope_id}
                                          — FULL pipeline (Demo or Production,
                                            per APP_MODE): Data Provider ->
                                            Context Builder -> Metrics Engine
                                            -> AI Enrichment -> Workload
                                            Engine -> Report Builder
  GET  /api/v1/workload/scopes           — available scopes/demo scenarios
  POST /api/v1/workload/analyse          — LEGACY: direct employee/task
                                            payload, deterministic-only,
                                            preserved for backward compat
  POST /api/v1/workload/simulate/{name}  — LEGACY: canned in-memory scenarios
  GET  /api/v1/workload/stream           — SSE real-time stream
  GET  /api/v1/workload/status           — last known report (polling)
"""

from __future__ import annotations
import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.core.exceptions import WorkloadServiceError
from app.data.sample_data import SAMPLE_SCENARIOS
from app.models.schemas import WorkloadUpdateRequest, WorkloadUpdateResponse
from app.services.balancer_service import BalancerService, get_balancer_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workload", tags=["workload-balancing"])


# ---------------------------------------------------------------------------
# Full pipeline — provider-driven (this is the feature the spec describes)
# ---------------------------------------------------------------------------

@router.post(
    "/analyze/{scope_type}/{scope_id}",
    summary="Run the full workload analysis pipeline for a project/team/workspace",
)
async def analyze_scope(
    scope_type: str,
    scope_id: str,
    svc: BalancerService = Depends(get_balancer_service),
) -> dict:
    """
    scope_type: "project" | "team" | "workspace"
    scope_id:   the real scope id (Production) OR a demo scenario name (Demo),
                e.g. "overloaded_team", "critical_project" — see GET /scopes.
    """
    if scope_type not in ("project", "team", "workspace"):
        raise HTTPException(status_code=400, detail="scope_type must be project, team, or workspace")
    try:
        return await svc.analyse_scope(scope_type, scope_id)
    except WorkloadServiceError as exc:
        logger.warning("analyze_scope business error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("analyze_scope failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/scopes", summary="List available scopes (Production) or demo scenarios (Demo)")
async def list_scopes(svc: BalancerService = Depends(get_balancer_service)) -> dict:
    settings = get_settings()
    scopes = await svc.list_scopes()
    return {"app_mode": settings.APP_MODE, "scopes": scopes}


@router.get("/mode", summary="Current app mode")
async def get_mode() -> dict:
    settings = get_settings()
    return {"app_mode": settings.APP_MODE}


# ---------------------------------------------------------------------------
# Legacy endpoint — direct employee/task payload, deterministic-only.
# Preserved so existing integrations keep working unchanged.
# ---------------------------------------------------------------------------

@router.post("/analyse", response_model=WorkloadUpdateResponse, summary="[Legacy] Analyse workload from a direct payload")
async def analyse_workload(
    request: WorkloadUpdateRequest,
    svc: BalancerService = Depends(get_balancer_service),
) -> WorkloadUpdateResponse:
    try:
        return await svc.analyse(request)
    except Exception as exc:
        logger.exception("analyse_workload failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/simulate/{scenario}", summary="[Legacy] Run a canned in-memory scenario")
async def simulate_scenario(
    scenario: str,
    svc: BalancerService = Depends(get_balancer_service),
) -> WorkloadUpdateResponse:
    """Available scenarios: balanced | overloaded | critical | mixed
    (kept from the pre-refactor implementation — for the new, DB-schema-aligned
    demo scenarios use POST /analyze/project/{scenario} in Demo mode instead)."""
    if scenario not in SAMPLE_SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown scenario '{scenario}'. Available: {list(SAMPLE_SCENARIOS)}",
        )
    request = WorkloadUpdateRequest(**SAMPLE_SCENARIOS[scenario])
    return await svc.analyse(request)


# ---------------------------------------------------------------------------
# SSE stream — real-time push
# ---------------------------------------------------------------------------

@router.get("/stream", summary="SSE real-time workload stream")
async def stream_workload(
    svc: BalancerService = Depends(get_balancer_service),
) -> StreamingResponse:
    """
    const es = new EventSource("/api/v1/workload/stream");
    es.onmessage = (e) => console.log(JSON.parse(e.data));
    """
    queue = svc.subscribe()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    payload = json.dumps(event.dict(), default=str)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            svc.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# Status endpoint — polling fallback
# ---------------------------------------------------------------------------

@router.get("/status", summary="Last known workload report")
async def get_status(svc: BalancerService = Depends(get_balancer_service)) -> dict:
    if svc._last_full_report is not None:
        return svc._last_full_report
    if svc._last_report is None:
        return {"message": "No analysis has been run yet. POST /analyze/{scope_type}/{scope_id} first."}
    return svc._last_report.dict()
