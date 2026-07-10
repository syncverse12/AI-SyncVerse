"""Centralized logging configuration for the Echo service."""
import logging
import sys

from app.core.config import settings


def configure_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]

    # Quiet down noisy third-party loggers unless we're debugging.
    for noisy in ("httpx", "chromadb", "urllib3", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(
            level if level <= logging.DEBUG else logging.WARNING
        )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
