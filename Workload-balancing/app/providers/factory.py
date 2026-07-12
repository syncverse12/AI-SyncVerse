"""
providers/factory.py
---------------------
Automatically selects DemoDataProvider or BackendDataProvider based on
APP_MODE. Nothing else in the codebase constructs a provider directly.
"""

from __future__ import annotations
from functools import lru_cache

from app.config import get_settings
from app.providers.base import BaseDataProvider
from app.providers.demo_provider import DemoDataProvider
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_data_provider() -> BaseDataProvider:
    settings = get_settings()
    if settings.APP_MODE == "production":
        # Imported lazily so `httpx`/`tenacity` aren't required just to run demo mode.
        from app.providers.backend_provider import BackendDataProvider
        logger.info("Provider factory: using BackendDataProvider")
        return BackendDataProvider()

    logger.info("Provider factory: using DemoDataProvider")
    return DemoDataProvider()
