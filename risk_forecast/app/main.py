"""
SyncVerse AI Risk Intelligence Engine — FastAPI Application
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes.risk_routes import router as risk_router
from app.core.config import settings
from app.core.database import lifespan_connections
from app.core.logging import configure_logging, get_logger
from app.rag.rag_service import RAGService
from app.ai.orchestrators.ai_orchestrator import get_orchestrator

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "SyncVerse Risk Intelligence Engine starting",
        version=settings.app_version,
        environment=settings.environment,
    )

    async with lifespan_connections():
        # Initialize Qdrant collections on startup
        try:
            orchestrator = get_orchestrator()
            rag = RAGService(orchestrator)
            await rag.ensure_collections()
            logger.info("Qdrant collections initialized ✓")
        except Exception as exc:
            logger.warning("Qdrant initialization failed", error=str(exc))

        yield

    logger.info("Risk Intelligence Engine shut down gracefully")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-powered proactive risk detection, prediction, and monitoring engine "
        "for SyncVerse project management platform."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(risk_router, prefix=settings.api_prefix)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health() -> dict:
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
