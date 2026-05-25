"""
app/main.py
FastAPI application factory with lifespan management.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.routers import health_router, alignment_router, ai_judge_router
from app.vector_store.qdrant_client import bootstrap_collections

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    configure_logging()
    settings = get_settings()
    logger.info("app_startup", env=settings.app_env)

    # Ensure Qdrant collections exist
    try:
        await bootstrap_collections()
        logger.info("qdrant_bootstrap_ok")
    except Exception as exc:
        logger.error("qdrant_bootstrap_failed", error=str(exc))
        # Don't crash – allow app to start; Qdrant may come up shortly

    yield

    logger.info("app_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Intelligent Project Management System",
        description=(
            "Enterprise-grade AI-powered project evaluation using "
            "FastAPI + Qdrant + OpenAI Embeddings + LLM Judge"
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health_router.router)
    app.include_router(alignment_router.router)
    app.include_router(ai_judge_router.router)

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error", "detail": str(exc)},
        )

    # ── Health probe ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def system_health():
        return {"status": "ok", "service": "intelligent-pm"}

    return app


app = create_app()
