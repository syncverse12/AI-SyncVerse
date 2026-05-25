"""
app/vector_store/retrieval.py
Semantic search helpers over Qdrant collections.
"""
from __future__ import annotations

from typing import Any, List

from qdrant_client.models import Filter, FieldCondition, MatchValue, ScoredPoint

from app.core.config import get_settings
from app.core.logging import get_logger
from app.vector_store.qdrant_client import get_qdrant_client

logger = get_logger(__name__)


def _project_filter(project_id: str) -> Filter:
    return Filter(
        must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
    )


async def search_similar(
    collection: str,
    query_vector: list[float],
    project_id: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
) -> List[ScoredPoint]:
    """
    Search a collection for the top-k most similar documents
    belonging to the given project.
    """
    settings = get_settings()
    client = await get_qdrant_client()
    k = top_k or settings.rag_top_k
    threshold = score_threshold or settings.rag_score_threshold

    results = await client.search(
        collection_name=collection,
        query_vector=query_vector,
        query_filter=_project_filter(project_id),
        limit=k,
        score_threshold=threshold,
        with_payload=True,
    )
    logger.debug(
        "qdrant_search",
        collection=collection,
        project_id=project_id,
        hits=len(results),
    )
    return results


async def fetch_all_by_project(
    collection: str,
    project_id: str,
    limit: int = 500,
) -> List[Any]:
    """Scroll through ALL records for a project (no vector needed)."""
    settings = get_settings()
    client = await get_qdrant_client()
    records, _ = await client.scroll(
        collection_name=collection,
        scroll_filter=_project_filter(project_id),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return records


async def fetch_by_ids(collection: str, ids: list[str]) -> List[Any]:
    """Retrieve specific points by their IDs."""
    client = await get_qdrant_client()
    return await client.retrieve(
        collection_name=collection,
        ids=ids,
        with_payload=True,
        with_vectors=False,
    )
