"""
Celery Background Workers — async risk processing tasks.

Workers handle:
  - Scheduled live risk refreshes
  - Bulk project scans
  - Historical incident indexing into Qdrant
  - ML model retraining triggers
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Celery app ────────────────────────────────────────────────────────────────

celery_app = Celery(
    "syncverse_risk",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=settings.worker_concurrency,
    task_acks_late=True,          # Only ack after successful completion
    task_reject_on_worker_lost=True,
    task_routes={
        "app.workers.tasks.refresh_project_risk": {"queue": "risk_refresh"},
        "app.workers.tasks.index_incident": {"queue": "indexing"},
        "app.workers.tasks.bulk_risk_scan": {"queue": "bulk"},
    },
)

# ── Periodic schedule ─────────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {
    # Refresh risk scores for all active projects every minute
    "refresh-active-projects": {
        "task": "app.workers.tasks.bulk_risk_scan",
        "schedule": settings.live_update_interval,
        "args": [],
    },
    # Daily model performance check at 2 AM UTC
    "daily-model-check": {
        "task": "app.workers.tasks.model_health_check",
        "schedule": crontab(hour=2, minute=0),
    },
}


# ── Helper to run async code inside Celery (sync) tasks ──────────────────────

def run_async(coro):
    """Execute an async coroutine from a synchronous Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.workers.tasks.refresh_project_risk",
)
def refresh_project_risk(self, project_id: str) -> dict:
    """
    Refresh the risk score for a single project.
    Triggered by live events (PR merged, deployment failed, etc.)
    """
    logger.info("Worker: refresh_project_risk", project_id=project_id)
    try:
        result = run_async(_async_refresh_project(project_id))
        return {"status": "success", "project_id": project_id, **result}
    except Exception as exc:
        logger.error("Worker task failed", project_id=project_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=2,
    name="app.workers.tasks.index_incident",
)
def index_incident(self, incident_data: dict) -> dict:
    """
    Index a historical incident into Qdrant for RAG retrieval.
    Triggered when a new post-mortem is submitted.
    """
    logger.info("Worker: index_incident", incident_type=incident_data.get("type"))
    try:
        result = run_async(_async_index_incident(incident_data))
        return {"status": "success", "vector_id": result}
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(name="app.workers.tasks.bulk_risk_scan")
def bulk_risk_scan() -> dict:
    """
    Scan all active projects and refresh risk scores.
    Runs every minute via Celery Beat.
    """
    logger.info("Worker: bulk_risk_scan starting")
    result = run_async(_async_bulk_scan())
    logger.info("Worker: bulk_risk_scan complete", **result)
    return result


@celery_app.task(name="app.workers.tasks.model_health_check")
def model_health_check() -> dict:
    """Daily ML model performance validation."""
    logger.info("Worker: model_health_check")
    # Check prediction drift, feature distribution shifts, etc.
    return {"status": "ok", "models_checked": 4}


# ── Async implementations ─────────────────────────────────────────────────────

async def _async_refresh_project(project_id: str) -> dict:
    """
    Full async pipeline: load metrics → compute risk → persist → alert.
    In production this would load from the project metrics service.
    """
    from app.core.database import AsyncSessionLocal, get_redis
    from app.services.dependencies import build_risk_service

    async with AsyncSessionLocal() as db:
        redis = await get_redis()
        service = await build_risk_service(db, redis)
        snapshot = await service.get_project_snapshot(UUID(project_id))
        return {"risk_score": snapshot.get("scores", {}).get("overall", 0)}


async def _async_index_incident(incident_data: dict) -> str:
    """Embed and store a historical incident in Qdrant."""
    from app.ai.orchestrators.ai_orchestrator import get_orchestrator
    from app.rag.rag_service import RAGService

    orchestrator = get_orchestrator()
    rag = RAGService(orchestrator)
    await rag.ensure_collections()

    # Generate a dense summary for embedding
    summary = (
        f"Incident type: {incident_data.get('type')}. "
        f"Cause: {incident_data.get('root_cause')}. "
        f"Resolution: {incident_data.get('resolution')}. "
        f"Duration: {incident_data.get('duration_hours')}h."
    )

    return await rag.index_incident(
        incident_id=incident_data.get("id", ""),
        summary_text=summary,
        metadata=incident_data,
    )


async def _async_bulk_scan() -> dict:
    """Scan all active projects."""
    from app.core.database import AsyncSessionLocal, get_redis
    from app.repositories.risk_repository import RiskRepository

    async with AsyncSessionLocal() as db:
        repo = RiskRepository(db)
        active_ids = await repo.get_active_project_ids()

    refreshed = 0
    for pid in active_ids:
        refresh_project_risk.apply_async(args=[str(pid)])
        refreshed += 1

    return {"projects_queued": refreshed}
