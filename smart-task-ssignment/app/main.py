"""
Smart Task Assignment System – FastAPI Application
===================================================
Entry point. Registers routers, lifespan events, middleware.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.utils.helpers import configure_logging
from app.services.realtime_engine import realtime_engine
from app.websocket.manager import manager
from app.routes.tasks import router as tasks_router
from app.routes.employees import router as employees_router

configure_logging(settings.log_level)
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

# NOTE: allow_credentials=True combined with allow_origins=["*"] is rejected by
# browsers (and disallowed by the fetch spec) — a wildcard origin cannot be
# paired with credentialed requests. Both values now come from Settings so a
# real origin list can be supplied via CORS_ORIGINS on Railway; credentials
# default to False, which is the only combination compatible with "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global exception handler ───────────────────────────────────────────────────
# Without this, an unhandled exception in a route still returns 500, but the
# traceback / exception message can leak to the client depending on server
# config, and nothing useful gets logged server-side. This guarantees a safe,
# consistent JSON error body and a server-side log entry for every 500.

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
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
        "environment": settings.environment,
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health():
    return {
        "status": "healthy",
        "ws_connections": manager.total_connections,
    }
