"""
balancer_routes.py
------------------
FastAPI router exposing:

  POST /api/v1/workload/analyse         — synchronous analysis
  GET  /api/v1/workload/stream          — SSE real-time stream
  GET  /api/v1/workload/status          — last known report (polling fallback)
  POST /api/v1/workload/simulate        — push canned scenarios for demos
"""

from __future__ import annotations
import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    BalanceReport,
    WorkloadUpdateRequest,
    WorkloadUpdateResponse,
)
from app.services.balancer_service import BalancerService, get_balancer_service
from app.data.sample_data import SAMPLE_SCENARIOS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workload", tags=["workload-balancing"])


# ---------------------------------------------------------------------------
# REST endpoint — trigger an analysis pass
# ---------------------------------------------------------------------------

@router.post("/analyse", response_model=WorkloadUpdateResponse, summary="Analyse workload")
async def analyse_workload(
    request: WorkloadUpdateRequest,
    svc: BalancerService = Depends(get_balancer_service),
) -> WorkloadUpdateResponse:
    """
    Submit employee + task data.  Returns a BalanceReport and broadcasts
    the result to all active SSE subscribers.
    """
    try:
        return await svc.analyse(request)
    except Exception as exc:
        logger.exception("analyse_workload failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# SSE stream — real-time push
# ---------------------------------------------------------------------------

@router.get("/stream", summary="SSE real-time workload stream")
async def stream_workload(
    svc: BalancerService = Depends(get_balancer_service),
) -> StreamingResponse:
    """
    Server-Sent Events stream.  Connect once; receive every analysis event
    and periodic heartbeat pings.

    Client usage:
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
                    # SSE keepalive comment
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            svc.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Status endpoint — polling fallback
# ---------------------------------------------------------------------------

@router.get("/status", summary="Last known workload report")
async def get_status(
    svc: BalancerService = Depends(get_balancer_service),
) -> dict:
    """
    Returns the most recently computed BalanceReport.
    Useful as a polling fallback when SSE is unavailable.
    """
    report = svc._last_report
    if report is None:
        return {"message": "No analysis has been run yet. POST to /analyse first."}
    return report.dict()


# ---------------------------------------------------------------------------
# Demo / simulation endpoint
# ---------------------------------------------------------------------------

@router.post("/simulate/{scenario}", summary="Run a pre-built demo scenario")
async def simulate_scenario(
    scenario: str,
    svc: BalancerService = Depends(get_balancer_service),
) -> WorkloadUpdateResponse:
    """
    Available scenarios: balanced | overloaded | critical | mixed
    """
    if scenario not in SAMPLE_SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown scenario '{scenario}'. Available: {list(SAMPLE_SCENARIOS)}",
        )
    request = WorkloadUpdateRequest(**SAMPLE_SCENARIOS[scenario])
    return await svc.analyse(request)
