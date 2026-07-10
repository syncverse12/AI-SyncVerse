"""FastAPI application entrypoint."""

from fastapi import FastAPI
from app.routers.risk_router import router as risk_router
from app.core.logging_config import configure_logging
from app.core.config import get_settings

settings = get_settings()
configure_logging(level=settings.log_level)

app = FastAPI(
    title="SyncVerse Risk Assessment Microservice",
    description=(
        "AI-powered risk assessment and recommendation microservice for "
        "AI-SyncVerse. Reads project data through the existing Backend API "
        "only — never accesses the database directly."
    ),
    version=settings.analysis_version,
)

app.include_router(risk_router)


@app.get("/health")
async def root_health():
    return {"status": "ok", "service": "risk-assessment-microservice"}
