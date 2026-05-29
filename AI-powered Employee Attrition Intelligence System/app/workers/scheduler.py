"""
Background Workers.
APScheduler-based scheduled jobs for periodic prediction recalculation.
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.core.config import settings
from app.db.session import AsyncSessionLocal


scheduler = AsyncIOScheduler()


async def recalculate_all_predictions() -> None:
    """
    Scheduled job: recalculate attrition predictions for all active employees.
    Runs every N hours as configured.
    """
    logger.info("Scheduled prediction recalculation starting...")

    from app.repositories.employee_repository import EmployeeRepository
    from app.services.attrition_service import AttritionService

    async with AsyncSessionLocal() as db:
        repo = EmployeeRepository(db)
        service = AttritionService(db)

        employees = await repo.get_all_active(limit=5000)
        logger.info(f"Recalculating predictions for {len(employees)} employees...")

        success = 0
        failed = 0
        for emp in employees:
            try:
                await service.predict_attrition(str(emp.id), trigger="scheduled")
                success += 1
            except Exception as exc:
                logger.warning(f"Scheduled prediction failed for {emp.id}: {exc}")
                failed += 1

        await db.commit()

    logger.info(
        f"Scheduled recalculation complete | "
        f"success={success} | failed={failed} | "
        f"completed_at={datetime.now(timezone.utc).isoformat()}"
    )


def start_scheduler() -> None:
    """Start the APScheduler with configured jobs."""
    if not settings.enable_background_jobs:
        logger.info("Background jobs disabled via config.")
        return

    interval_hours = settings.prediction_recalc_interval_hours

    scheduler.add_job(
        recalculate_all_predictions,
        trigger=IntervalTrigger(hours=interval_hours),
        id="recalculate_predictions",
        name="Periodic Attrition Recalculation",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )

    scheduler.start()
    logger.info(
        f"Scheduler started | prediction recalc every {interval_hours}h"
    )


def stop_scheduler() -> None:
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
