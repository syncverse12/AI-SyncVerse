"""
Database & cache connections — async-first, lifecycle-managed.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── SQLAlchemy ─────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.postgres_dsn,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Redis ──────────────────────────────────────────────────────────────────────

_redis_pool: aioredis.Redis | None = None
_pubsub_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return the shared Redis connection (general-purpose cache)."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def get_pubsub_redis() -> aioredis.Redis:
    """Return the dedicated Pub/Sub Redis connection."""
    global _pubsub_pool
    if _pubsub_pool is None:
        _pubsub_pool = await aioredis.from_url(
            settings.redis_pubsub_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _pubsub_pool


@asynccontextmanager
async def lifespan_connections():
    """Initialize and teardown all connections — used in FastAPI lifespan."""
    logger.info("Connecting to PostgreSQL and Redis…")
    redis = await get_redis()
    await redis.ping()
    logger.info("Redis connected ✓")
    yield
    logger.info("Shutting down connections…")
    if _redis_pool:
        await _redis_pool.aclose()
    if _pubsub_pool:
        await _pubsub_pool.aclose()
    await engine.dispose()
    logger.info("All connections closed ✓")
