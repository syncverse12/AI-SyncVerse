"""
app/vector_store/qdrant_client.py
Qdrant client singleton + collection bootstrap.
"""
from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PayloadSchemaType,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: Optional[AsyncQdrantClient] = None
_lock = asyncio.Lock()


async def get_qdrant_client() -> AsyncQdrantClient:
    """Return (and lazily create) the shared async Qdrant client."""
    global _client
    if _client is None:
        async with _lock:
            if _client is None:
                settings = get_settings()
                kwargs: dict = {
                    "host": settings.qdrant_host,
                    "port": settings.qdrant_port,
                }
                if settings.qdrant_api_key:
                    kwargs["api_key"] = settings.qdrant_api_key
                    kwargs["https"] = True
                _client = AsyncQdrantClient(**kwargs)
                logger.info("qdrant_client_created", host=settings.qdrant_host)
    return _client


async def bootstrap_collections() -> None:
    """Ensure all required Qdrant collections exist at startup."""
    settings = get_settings()
    client = await get_qdrant_client()
    dim = settings.openai_embedding_dimensions

    collections = [
        settings.qdrant_collection_requirements,
        settings.qdrant_collection_tasks,
        settings.qdrant_collection_deliverables,
        settings.qdrant_collection_notes,
    ]

    existing = {c.name for c in (await client.get_collections()).collections}

    for name in collections:
        if name not in existing:
            await client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            # Create payload index on project_id for fast filtering
            await client.create_payload_index(
                collection_name=name,
                field_name="project_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            logger.info("collection_created", collection=name)
        else:
            logger.info("collection_exists", collection=name)
