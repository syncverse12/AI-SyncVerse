"""SQLAlchemy engine, session factory, and FastAPI dependency."""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.base import Base

logger = get_logger(__name__)

_DATABASE_URL = settings.effective_database_url
_IS_SQLITE = _DATABASE_URL.startswith("sqlite")

if _IS_SQLITE:
    logger.warning(
        "DATABASE_URL not set - falling back to local SQLite at %s. "
        "This is fine for a quick deploy or local testing, but a managed "
        "PostgreSQL database is recommended for production so data isn't "
        "lost if the container's ephemeral filesystem is reset.",
        settings.SQLITE_PATH,
    )
    engine = create_engine(
        _DATABASE_URL,
        connect_args={"check_same_thread": False},
        future=True,
    )
else:
    engine = create_engine(
        _DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def init_db() -> None:
    """Create all tables that don't yet exist. Safe to call on every boot."""
    from app.models import (  # noqa: F401  (ensures models are registered)
        memory,
        project,
        task,
        risk,
        team,
        comment,
        documentation,
        technical_decision,
        meeting,
        requirement,
        conversation,
    )

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for use outside of FastAPI request handling
    (e.g. background jobs, automatic memory collectors)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
