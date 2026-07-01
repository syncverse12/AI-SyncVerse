"""
app/services/embedding_service.py
Generate text embeddings using Google Gemini.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def _embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Embed multiple texts concurrently while limiting the number of
    simultaneous API requests to avoid rate limits.
    """
    settings = get_settings()
    client = _get_client()

    # Maximum concurrent embedding requests
    semaphore = asyncio.Semaphore(10)

    async def _embed_one(text: str) -> List[float]:
        async with semaphore:
            response = await asyncio.to_thread(
                client.models.embed_content,
                model=settings.gemini_embedding_model,
                contents=[text],
            )
            return response.embeddings[0].values

    tasks = [_embed_one(text) for text in texts]
    return await asyncio.gather(*tasks)


async def embed_text(text: str) -> List[float]:
    """Embed a single text string."""
    [vector] = await _embed_batch([text])
    return vector


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Batch embed multiple texts.
    """
    if not texts:
        return []

    vectors = await _embed_batch(texts)

    logger.info(
        "embeddings_generated",
        total=len(texts),
    )

    return vectors


async def build_embeddings_map(texts: List[str]) -> dict[str, List[float]]:
    """Return {text: vector} mapping for a list of unique texts."""
    unique = list(dict.fromkeys(texts))  # deduplicate, preserve order
    vectors = await embed_texts(unique)
    return dict(zip(unique, vectors))
