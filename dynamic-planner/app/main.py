"""
app/main.py
-----------
FastAPI application factory and uvicorn entry point.

Run locally:
    uvicorn app.main:app --reload --port 7860

Production / Docker / Hugging Face Spaces:
    uvicorn app.main:app --host 0.0.0.0 --port 7860 --workers 1
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.utils.version import VERSION

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("service")


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  AI Dynamic Project Planner  v%s", VERSION)
    logger.info("  Swagger UI  →  /docs")
    logger.info("  ReDoc       →  /redoc")
    logger.info("  Health      →  /health")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    yield
    logger.info("AI Planning Service shutting down.")


# ── App factory ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Dynamic Project Planner",
        description=(
            "A rule-based AI scheduling engine that builds, optimises, and\n"
            "dynamically replans project timelines — no ML training required.\n\n"
            "## Quickstart\n"
            "1. `POST /plan` — submit tasks, resources, deadline → full schedule\n"
            "2. `GET  /plan/{id}` — retrieve the plan\n"
            "3. `POST /plan/{id}/replan` — send a change event → updated schedule\n\n"
            "## Algorithms\n"
            "- **DAG** dependency graph + Kahn cycle detection\n"
            "- **CPM** critical path — forward/backward pass, float analysis\n"
            "- **Resource levelling** — skill matching + capacity-aware scheduling\n"
            "- **Sprint grouping** — heuristic load balancing\n"
            "- **Event-driven replanning** — 7 event types, targeted rescheduling\n"
        ),
        version=VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global error handler ──────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error":     "internal_server_error",
                "detail":    "An unexpected error occurred. Check service logs.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(router)

    return app


# ── Application instance ───────────────────────────────────────────────────────

app = create_app()


# ── Dev entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "7860")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
        log_level="info",
    )
