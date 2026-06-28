"""
SyncVerse Attrition Intelligence System — FastAPI Application Entry Point.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import SyncVerseBaseException
from app.ml.predict import model_registry
from app.api.v1.router import api_router, root_router


# ──────────────────────────────────────────────
# Optional DB / Scheduler Imports
# ──────────────────────────────────────────────

HF_MODE = os.getenv("APP_ENV") == "hf"

if not HF_MODE:
    from app.db.session import init_db, close_db
    from app.workers.scheduler import start_scheduler, stop_scheduler


# ──────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting SyncVerse API")

    # ── Database only outside HF ──
    if not HF_MODE:
        await init_db()
        logger.info("Database initialized")
    else:
        logger.warning("HF mode detected → skipping DB init")

    # ── ML Models ──
    model_registry.load_models()
    logger.info("ML models loaded")

    # ── Scheduler only outside HF ──
    if not HF_MODE:
        start_scheduler()
        logger.info("Scheduler started")

    yield

    # ── Shutdown ──
    if not HF_MODE:
        stop_scheduler()
        await close_db()
        logger.info("Database closed")

    logger.info("Shutdown complete")


# ──────────────────────────────────────────────
# App Factory
# ──────────────────────────────────────────────

def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Production-ready AI-powered Employee Attrition "
            "Intelligence System for SyncVerse."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ──────────────────────────────────────────
    # Middleware
    # ──────────────────────────────────────────

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000
    )

    # ──────────────────────────────────────────
    # Exception Handlers
    # ──────────────────────────────────────────

    @app.exception_handler(SyncVerseBaseException)
    async def syncverse_exception_handler(
        request: Request,
        exc: SyncVerseBaseException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": exc.code,
                "message": exc.message,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "message": (
                    "An unexpected error occurred. "
                    "Please try again."
                ),
            },
        )

    # ──────────────────────────────────────────
    # Routers
    # ──────────────────────────────────────────

    app.include_router(api_router)
    app.include_router(root_router)

    # ──────────────────────────────────────────
    # Root Endpoint
    # ──────────────────────────────────────────

    @app.get("/", tags=["Root"], include_in_schema=False)
    async def root():
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
            "docs": "/docs",
            "health": "/health",
        }

    return app


# ──────────────────────────────────────────────
# App Instance
# ──────────────────────────────────────────────

app = create_application()


# ──────────────────────────────────────────────
# Local Development Entry
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=7860,
        reload=False,
        workers=1,
        log_level=settings.log_level.lower(),
    )