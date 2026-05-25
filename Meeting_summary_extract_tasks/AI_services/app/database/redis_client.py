import json
import aioredis
from typing import Any, Optional
from AI_services.app.config import settings


_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


async def publish(channel: str, payload: Any):
    r = await get_redis()
    await r.publish(channel, json.dumps(payload))


async def set_value(key: str, value: Any, ttl: int = 3600):
    r = await get_redis()
    await r.set(key, json.dumps(value), ex=ttl)


async def get_value(key: str) -> Optional[Any]:
    r = await get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def append_to_list(key: str, value: Any, ttl: int = 86400):
    r = await get_redis()
    await r.rpush(key, json.dumps(value))
    await r.expire(key, ttl)


async def get_list(key: str) -> list:
    r = await get_redis()
    items = await r.lrange(key, 0, -1)
    return [json.loads(i) for i in items]


async def delete_key(key: str):
    r = await get_redis()
    await r.delete(key)
