"""
main.py
-------
FastAPI application factory for the Dynamic Workload Balancing System.

Run:
    uvicorn app.main:app --reload --port 8000

Docs:
    http://localhost:8000/docs
"""

from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.balancer_routes import router as balancer_router
from app.services.balancer_service import get_balancer_service

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("workload_balancer")


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown tasks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("⚖️  Dynamic Workload Balancing System starting up…")

    svc = get_balancer_service()

    # Background heartbeat task (30s interval)
    async def heartbeat():
        while True:
            await asyncio.sleep(30)
            await svc.ping_all()

    hb_task = asyncio.create_task(heartbeat())
    logger.info("✅ Heartbeat task started")

    yield

    hb_task.cancel()
    logger.info("🛑 Workload Balancing System shut down cleanly")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="⚖️ Dynamic Workload Balancing System",
    description=(
        "Real-time workload monitoring, imbalance detection, and redistribution "
        "recommendations for engineering teams.  All actions require human approval."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS (tighten allowed_origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(balancer_router)


# ---------------------------------------------------------------------------
# Health-check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "workload-balancer"}
