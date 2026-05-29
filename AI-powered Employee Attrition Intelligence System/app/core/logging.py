"""
Centralized logging configuration using Loguru.
"""

import sys
import os
from loguru import logger
from app.core.config import settings


def setup_logging() -> None:
    """Configure application-wide logging."""
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Console handler
    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=not settings.is_production,
    )

    # File handler
    os.makedirs(os.path.dirname(settings.log_file), exist_ok=True)
    logger.add(
        settings.log_file,
        format=log_format,
        level=settings.log_level,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        backtrace=True,
        diagnose=not settings.is_production,
        enqueue=True,  # async-safe
    )

    logger.info(
        f"Logging initialized | env={settings.app_env} | level={settings.log_level}"
    )
