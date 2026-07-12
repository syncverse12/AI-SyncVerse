"""
main.py
-------
FastAPI application factory for the Dynamic Workload Balancing System.

Run:
    uvicorn app.main:app --reload --port 7860

Docs:
    http://localhost:7860/docs
"""

from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging import get_logger, configure_logging
from app.routes.balancer_routes import router as balancer_router
from app.services.balancer_service import get_balancer_service

configure_logging()
logger = get_logger("workload_balancer")
settings = get_settings()


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown tasks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Workload Analysis service starting up in APP_MODE={settings.APP_MODE}")

    svc = get_balancer_service()

    async def heartbeat():
        while True:
            await asyncio.sleep(30)
            await svc.ping_all()

    hb_task = asyncio.create_task(heartbeat())
    logger.info("Heartbeat task started")

    yield

    hb_task.cancel()
    logger.info("Workload Analysis service shut down cleanly")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SyncVerse Workload Analysis Service",
    description=(
        "AI-enriched workload monitoring, imbalance detection, and redistribution "
        "recommendations for SyncVerse engineering teams. Deterministic metrics are "
        "computed in Python; only genuinely un-derivable metrics are AI-estimated. "
        "All redistribution actions require human approval."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(balancer_router)


# ---------------------------------------------------------------------------
# Health-check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "workload-analysis", "app_mode": settings.APP_MODE}
