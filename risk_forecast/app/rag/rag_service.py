"""
RAG Service — Qdrant-backed retrieval augmented generation.

Stores embeddings for:
  - project summaries
  - incidents & post-mortems
  - sprint retrospectives
  - risk reports
  - meeting summaries

Retrieves similar historical cases before AI risk generation to ground
predictions in real company memory rather than generic knowledge.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RAGService:
    """
    Manages vector storage and semantic search for historical project memory.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._client: AsyncQdrantClient | None = None
        self._orchestrator = orchestrator

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
            )
        return self._client

    # ── Collection management ────────────────────────────────────────────────

    async def ensure_collections(self) -> None:
        """Create Qdrant collections if they don't exist yet."""
        collections = [
            settings.qdrant_projects_collection,
            settings.qdrant_incidents_collection,
            settings.qdrant_retrospectives_collection,
        ]
        for name in collections:
            existing = await self.client.get_collections()
            existing_names = {c.name for c in existing.collections}
            if name not in existing_names:
                await self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=settings.qdrant_vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection", collection=name)

    # ── Indexing ─────────────────────────────────────────────────────────────

    async def index_project_summary(
        self,
        project_id: str,
        summary_text: str,
        metadata: dict[str, Any],
    ) -> str:
        """Embed and store a project summary for future retrieval."""
        vector = await self._orchestrator.embed(summary_text)
        point_id = str(uuid.uuid4())

        await self.client.upsert(
            collection_name=settings.qdrant_projects_collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "project_id": project_id,
                        "text": summary_text,
                        **metadata,
                    },
                )
            ],
        )
        logger.debug("Indexed project summary", project_id=project_id, point_id=point_id)
        return point_id

    async def index_incident(
        self,
        incident_id: str,
        summary_text: str,
        metadata: dict[str, Any],
    ) -> str:
        """Embed and store an incident report."""
        vector = await self._orchestrator.embed(summary_text)
        point_id = str(uuid.uuid4())

        await self.client.upsert(
            collection_name=settings.qdrant_incidents_collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "incident_id": incident_id,
                        "text": summary_text,
                        **metadata,
                    },
                )
            ],
        )
        return point_id

    # ── Retrieval ────────────────────────────────────────────────────────────

    async def find_similar_projects(
        self,
        query_text: str,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the most similar historical projects.
        Returns formatted context strings for LLM prompt injection.
        """
        k = top_k or settings.rag_top_k
        threshold = score_threshold or settings.rag_score_threshold

        query_vector = await self._orchestrator.embed(query_text)

        results: list[ScoredPoint] = await self.client.search(
            collection_name=settings.qdrant_projects_collection,
            query_vector=query_vector,
            limit=k,
            score_threshold=threshold,
            with_payload=True,
        )

        return self._format_results(results)

    async def find_similar_incidents(
        self,
        query_text: str,
        incident_type: str | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve similar historical incidents, optionally filtered by type."""
        k = top_k or settings.rag_top_k
        query_vector = await self._orchestrator.embed(query_text)

        search_filter = None
        if incident_type:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="incident_type",
                        match=MatchValue(value=incident_type),
                    )
                ]
            )

        results = await self.client.search(
            collection_name=settings.qdrant_incidents_collection,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=k,
            score_threshold=settings.rag_score_threshold,
            with_payload=True,
        )

        return self._format_results(results)

    # ── Context building ─────────────────────────────────────────────────────

    async def build_historical_context(self, project_description: str) -> str:
        """
        Build a rich historical context string to inject into LLM prompts.
        Combines similar projects and incidents.
        """
        similar_projects = await self.find_similar_projects(project_description)
        similar_incidents = await self.find_similar_incidents(project_description)

        if not similar_projects and not similar_incidents:
            return "No similar historical cases found in company memory."

        parts = []

        if similar_projects:
            parts.append("SIMILAR HISTORICAL PROJECTS:")
            for i, p in enumerate(similar_projects, 1):
                parts.append(
                    f"{i}. [Similarity: {p['score']:.0%}] {p['text'][:400]}"
                )

        if similar_incidents:
            parts.append("\nRELATED HISTORICAL INCIDENTS:")
            for i, inc in enumerate(similar_incidents, 1):
                parts.append(
                    f"{i}. [Similarity: {inc['score']:.0%}] {inc['text'][:400]}"
                )

        return "\n".join(parts)

    # ── Utils ────────────────────────────────────────────────────────────────

    @staticmethod
    def _format_results(results: list[ScoredPoint]) -> list[dict[str, Any]]:
        formatted = []
        for r in results:
            payload = r.payload or {}
            formatted.append(
                {
                    "score": r.score,
                    "text": payload.get("text", ""),
                    "metadata": {k: v for k, v in payload.items() if k != "text"},
                }
            )
        return formatted
