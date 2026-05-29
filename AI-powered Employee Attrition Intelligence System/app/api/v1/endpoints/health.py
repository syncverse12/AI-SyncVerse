"""
Health Check Endpoint.
"""

from datetime import datetime, timezone
from fastapi import APIRouter
from loguru import logger

from app.core.config import settings
from app.ml.predict import model_registry
from app.schemas.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
)
async def health_check() -> HealthResponse:
    """
    Returns service health status including:
    - Database connectivity
    - Redis availability
    - ML model load status
    """
    # Database check
    db_status = "unknown"
    try:
        from app.db.session import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "healthy"
    except Exception as exc:
        logger.warning(f"DB health check failed: {exc}")
        db_status = "unhealthy"

    # Redis check
    redis_status = "unknown"
    try:
        import aioredis
        redis = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await redis.ping()
        await redis.close()
        redis_status = "healthy"
    except Exception:
        redis_status = "unavailable"

    # ML model status
    ml_models = {
        "attrition_model": model_registry.attrition_model is not None,
        "promotion_model": model_registry.promotion_model is not None,
        "preprocessor": model_registry.preprocessor is not None,
    }

    overall = (
        "healthy"
        if db_status == "healthy" and any(ml_models.values())
        else "degraded"
    )

    return HealthResponse(
        status=overall,
        version=settings.app_version,
        environment=settings.app_env,
        database=db_status,
        redis=redis_status,
        ml_models=ml_models,
        timestamp=datetime.now(timezone.utc),
    )
