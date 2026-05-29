"""
Redis cache utility.
Optional caching layer for prediction results and computed data.
"""

from __future__ import annotations
import json
from typing import Any, Optional
from loguru import logger

from app.core.config import settings


class CacheService:
    """Async Redis cache wrapper with graceful degradation."""

    _client = None

    @classmethod
    async def get_client(cls):
        if cls._client is None:
            try:
                import aioredis
                cls._client = aioredis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
            except Exception as exc:
                logger.warning(f"Redis connection failed: {exc}. Cache disabled.")
                return None
        return cls._client

    @classmethod
    async def get(cls, key: str) -> Optional[Any]:
        client = await cls.get_client()
        if client is None:
            return None
        try:
            value = await client.get(key)
            return json.loads(value) if value else None
        except Exception as exc:
            logger.debug(f"Cache GET error for '{key}': {exc}")
            return None

    @classmethod
    async def set(cls, key: str, value: Any, ttl: int = None) -> bool:
        client = await cls.get_client()
        if client is None:
            return False
        try:
            ttl = ttl or settings.redis_cache_ttl
            await client.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception as exc:
            logger.debug(f"Cache SET error for '{key}': {exc}")
            return False

    @classmethod
    async def delete(cls, key: str) -> bool:
        client = await cls.get_client()
        if client is None:
            return False
        try:
            await client.delete(key)
            return True
        except Exception as exc:
            logger.debug(f"Cache DELETE error for '{key}': {exc}")
            return False

    @classmethod
    async def invalidate_employee(cls, employee_id: str) -> None:
        """Invalidate all cached predictions for an employee."""
        patterns = [
            f"attrition:{employee_id}",
            f"promotion:{employee_id}",
        ]
        for key in patterns:
            await cls.delete(key)

    @staticmethod
    def attrition_key(employee_id: str) -> str:
        return f"attrition:{employee_id}"

    @staticmethod
    def promotion_key(employee_id: str) -> str:
        return f"promotion:{employee_id}"

    @staticmethod
    def team_key(team_id: str) -> str:
        return f"team_risk:{team_id}"


cache = CacheService()
