"""FastAPI routes. Thin — delegates everything to the Orchestrator."""

import logging
from fastapi import APIRouter, HTTPException, Depends
import httpx

from app.services.risk_report_service import generate_risk_report, get_report_history
from app.schemas.report_schema import RiskReport
from app.exceptions.collector import ProjectNotFoundError, BackendUnavailableError
from app.core.http_client import build_http_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["risk"])


async def get_http_client():
    client = build_http_client()
    try:
        yield client
    finally:
        await client.aclose()


@router.post("/{project_id}/analyze", response_model=RiskReport)
async def analyze_project(project_id: str, http_client: httpx.AsyncClient = Depends(get_http_client)):
    try:
        return await generate_risk_report(project_id, http_client)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BackendUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Backend unavailable: {exc.reason}")


@router.get("/{project_id}/risk-report", response_model=RiskReport)
async def get_latest_risk_report(project_id: str, http_client: httpx.AsyncClient = Depends(get_http_client)):
    # For simplicity, GET regenerates the latest report. A caching layer
    # (see app/cache/) can later short-circuit this within a TTL window.
    try:
        return await generate_risk_report(project_id, http_client)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BackendUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Backend unavailable: {exc.reason}")


@router.get("/{project_id}/history")
async def get_history(project_id: str, limit: int = 20):
    reports = await get_report_history(project_id, limit=limit)
    return {"project_id": project_id, "count": len(reports), "reports": reports}
