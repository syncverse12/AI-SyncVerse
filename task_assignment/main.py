"""
Smart Task Assignment System – FastAPI Application
===================================================
Entry point. Registers routers, lifespan events, middleware.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.utils.helpers import configure_logging
from app.services.realtime_engine import realtime_engine
from app.routes.tasks import router as tasks_router
from app.routes.employees import router as employees_router

configure_logging("INFO")
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Real-Time Task Assignment System…")
    await realtime_engine.start()
    yield
    logger.info("Shutting down…")
    await realtime_engine.stop()


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Real-Time Agent-Based Smart Task Assignment System",
    description=(
        "Multi-agent FastAPI system that receives tasks, analyses them using five "
        "independent AI agents, and streams ranked employee recommendations in real time "
        "via WebSockets."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(tasks_router)
app.include_router(employees_router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
async def root():
    return {
        "service": "Smart Task Assignment System",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health():
    from app.websocket.manager import manager
    return {
        "status": "healthy",
        "ws_connections": manager.total_connections,
    }
