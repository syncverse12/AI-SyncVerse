"""
SyncVerse Attrition Intelligence System — FastAPI Application Entry Point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import SyncVerseBaseException
from app.db.session import init_db, close_db
from app.ml.predict import model_registry
from app.workers.scheduler import start_scheduler, stop_scheduler
from app.api.v1.router import api_router, root_router


# ──────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init resources on startup, clean up on shutdown."""
    setup_logging()
    logger.info(f"Starting {settings.app_name} v{settings.app_version} [{settings.app_env}]")

    # Initialize DB
    await init_db()
    logger.info("Database initialized.")

    # Load ML models
    model_registry.load_models()

    # Start background scheduler
    start_scheduler()

    yield  # ← application is running

    # Shutdown
    stop_scheduler()
    await close_db()
    logger.info(f"{settings.app_name} shutdown complete.")


# ──────────────────────────────────────────────
# App Factory
# ──────────────────────────────────────────────

def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Production-ready AI-powered Employee Attrition Intelligence System for SyncVerse. "
            "Predicts attrition risk, recommends promotions, and explains decisions."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Exception Handlers ──
    @app.exception_handler(SyncVerseBaseException)
    async def syncverse_exception_handler(
        request: Request, exc: SyncVerseBaseException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": exc.code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again.",
            },
        )

    # ── Routers ──
    app.include_router(api_router)
    app.include_router(root_router)  # /health at root

    # ── Root endpoint ──
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


app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=not settings.is_production,
        workers=1 if not settings.is_production else settings.workers,
        log_level=settings.log_level.lower(),
    )
