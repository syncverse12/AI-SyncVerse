"""
app/services/embedding_service.py
Generate and cache text embeddings via OpenAI.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import List, Optional

import redis.asyncio as aioredis
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis: Optional[aioredis.Redis] = None
_openai: Optional[AsyncOpenAI] = None
_lock = asyncio.Lock()


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        async with _lock:
            if _redis is None:
                settings = get_settings()
                _redis = aioredis.from_url(
                    settings.redis_url, encoding="utf-8", decode_responses=True
                )
    return _redis


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        settings = get_settings()
        _openai = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai


def _cache_key(text: str, model: str) -> str:
    digest = hashlib.sha256(f"{model}:{text}".encode()).hexdigest()
    return f"emb:{digest}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def _embed_batch(texts: List[str]) -> List[List[float]]:
    settings = get_settings()
    client = _get_openai()
    response = await client.embeddings.create(
        input=texts,
        model=settings.openai_embedding_model,
        dimensions=settings.openai_embedding_dimensions,
    )
    return [item.embedding for item in response.data]


async def embed_text(text: str) -> List[float]:
    """Embed a single text string, using Redis cache."""
    settings = get_settings()
    redis = await _get_redis()
    key = _cache_key(text, settings.openai_embedding_model)

    cached = await redis.get(key)
    if cached:
        return json.loads(cached)

    [vector] = await _embed_batch([text])
    await redis.setex(key, settings.embedding_cache_ttl, json.dumps(vector))
    return vector


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Batch-embed texts, checking the cache for each.
    Returns vectors in the same order as input.
    """
    settings = get_settings()
    redis = await _get_redis()
    model = settings.openai_embedding_model

    results: List[Optional[List[float]]] = [None] * len(texts)
    missing_indices: List[int] = []

    # Cache lookup
    for i, text in enumerate(texts):
        key = _cache_key(text, model)
        cached = await redis.get(key)
        if cached:
            results[i] = json.loads(cached)
        else:
            missing_indices.append(i)

    if missing_indices:
        missing_texts = [texts[i] for i in missing_indices]

        # Batch in chunks of 100 (OpenAI limit)
        BATCH = 100
        fresh_vectors: List[List[float]] = []
        for start in range(0, len(missing_texts), BATCH):
            chunk = missing_texts[start : start + BATCH]
            fresh_vectors.extend(await _embed_batch(chunk))

        # Cache and assign
        pipe = redis.pipeline()
        for idx, vec in zip(missing_indices, fresh_vectors):
            results[idx] = vec
            key = _cache_key(texts[idx], model)
            pipe.setex(key, settings.embedding_cache_ttl, json.dumps(vec))
        await pipe.execute()

        logger.info(
            "embeddings_generated",
            total=len(texts),
            cached=len(texts) - len(missing_indices),
            fresh=len(missing_indices),
        )

    return results  # type: ignore[return-value]


async def build_embeddings_map(texts: List[str]) -> dict[str, List[float]]:
    """Return {text: vector} mapping for a list of unique texts."""
    unique = list(dict.fromkeys(texts))  # deduplicate, preserve order
    vectors = await embed_texts(unique)
    return dict(zip(unique, vectors))
