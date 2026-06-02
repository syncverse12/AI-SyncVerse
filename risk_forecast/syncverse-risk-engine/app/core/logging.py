"""
Structured logging — JSON in production, human-readable in dev.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings


def _add_severity(logger: Any, method: str, event_dict: EventDict) -> EventDict:
    """Map structlog levels to GCP/Datadog severity labels."""
    level = event_dict.get("level", method).upper()
    event_dict["severity"] = level
    return event_dict


def configure_logging() -> None:
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _add_severity,
    ]

    if settings.is_production:
        # Machine-readable JSON for log aggregation
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        # Pretty console output for local dev
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "openai", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
