"""
Dependency injection — wires all services together for FastAPI.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrators.ai_orchestrator import AIOrchestrator, get_orchestrator
from app.alerts.alert_engine import AlertEngine
from app.core.database import get_db, get_redis
from app.ml.models.predictor import MLPredictor
from app.rag.rag_service import RAGService
from app.repositories.risk_repository import AlertRepository, RiskRepository
from app.services.risk_service import RiskService

import redis.asyncio as aioredis


async def get_risk_repository(db: AsyncSession = Depends(get_db)) -> RiskRepository:
    return RiskRepository(db)


async def get_alert_repository(db: AsyncSession = Depends(get_db)) -> AlertRepository:
    return AlertRepository(db)


async def get_rag_service(
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
) -> RAGService:
    return RAGService(orchestrator)


async def get_ml_predictor() -> MLPredictor:
    return MLPredictor()


async def get_alert_engine(
    redis: aioredis.Redis = Depends(get_redis),
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
    alert_repo: AlertRepository = Depends(get_alert_repository),
) -> AlertEngine:
    return AlertEngine(redis, orchestrator, alert_repo)


async def get_risk_service(
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
    rag_service: RAGService = Depends(get_rag_service),
    ml_predictor: MLPredictor = Depends(get_ml_predictor),
    alert_engine: AlertEngine = Depends(get_alert_engine),
    repository: RiskRepository = Depends(get_risk_repository),
    redis: aioredis.Redis = Depends(get_redis),
) -> RiskService:
    return RiskService(
        orchestrator=orchestrator,
        rag_service=rag_service,
        ml_predictor=ml_predictor,
        alert_engine=alert_engine,
        repository=repository,
        redis=redis,
    )


async def build_risk_service(
    db: AsyncSession, redis: aioredis.Redis
) -> RiskService:
    """Used in Celery workers (no FastAPI DI available)."""
    orchestrator = get_orchestrator()
    rag = RAGService(orchestrator)
    ml = MLPredictor()
    alert_repo = AlertRepository(db)
    risk_repo = RiskRepository(db)
    alert_engine = AlertEngine(redis, orchestrator, alert_repo)
    return RiskService(
        orchestrator=orchestrator,
        rag_service=rag,
        ml_predictor=ml,
        alert_engine=alert_engine,
        repository=risk_repo,
        redis=redis,
    )
