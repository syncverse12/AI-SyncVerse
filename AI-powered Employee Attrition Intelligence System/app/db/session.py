"""
Async SQLAlchemy database engine and session management.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from loguru import logger
from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def create_engine() -> AsyncEngine:
    """Create async SQLAlchemy engine with connection pooling."""
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_pre_ping=True,
        echo=settings.debug,
        future=True,
    )
    return engine


engine: AsyncEngine = create_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(f"Database session error: {exc}")
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables on startup."""
    from app.models import (  # noqa: F401 - trigger imports to register models
        employee,
        metrics,
        predictions,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized.")


async def close_db() -> None:
    """Dispose engine on shutdown."""
    await engine.dispose()
    logger.info("Database engine disposed.")
