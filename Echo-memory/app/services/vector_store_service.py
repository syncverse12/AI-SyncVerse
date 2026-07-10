"""ChromaDB-backed semantic memory index.

Each project gets its own Chroma collection so retrieval never leaks
context between projects, while still letting Echo search across every
team within a single project's collection (team is stored as metadata for
optional filtering).
"""
import uuid
from functools import lru_cache
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.embedding_service import get_embedding_service

logger = get_logger(__name__)


class VectorStoreService:
    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._embedding_service = get_embedding_service()

    def _collection_name(self, project_id: uuid.UUID) -> str:
        return f"{settings.CHROMA_COLLECTION_PREFIX}_{str(project_id).replace('-', '')}"

    def _get_collection(self, project_id: uuid.UUID):
        return self._client.get_or_create_collection(
            name=self._collection_name(project_id),
            metadata={"project_id": str(project_id)},
        )

    def upsert_memory(
        self,
        memory_id: uuid.UUID,
        project_id: uuid.UUID,
        document_text: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Embed and store a memory. Returns the Chroma document id."""
        collection = self._get_collection(project_id)
        embedding = self._embedding_service.embed_text(document_text)
        doc_id = str(memory_id)
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[document_text],
            metadatas=[self._sanitize_metadata(metadata)],
        )
        return doc_id

    def query(
        self,
        project_id: uuid.UUID,
        query_text: str,
        top_k: int = 8,
        team_name: Optional[str] = None,
        memory_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        collection = self._get_collection(project_id)
        if collection.count() == 0:
            return []

        where: Dict[str, Any] = {}
        if team_name:
            where["team_name"] = team_name
        if memory_type:
            where["memory_type"] = memory_type

        query_embedding = self._embedding_service.embed_text(query_text)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, max(collection.count(), 1)),
            where=where or None,
        )

        output: List[Dict[str, Any]] = []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]

        for doc_id, distance, metadata, document in zip(ids, distances, metadatas, documents):
            # Chroma returns cosine distance by default; convert to a
            # 0-1 similarity score that's intuitive as a "relevance score".
            similarity = max(0.0, 1.0 - distance / 2.0)
            output.append(
                {
                    "id": doc_id,
                    "score": similarity,
                    "metadata": metadata,
                    "document": document,
                }
            )
        return output

    def delete_memory(self, project_id: uuid.UUID, memory_id: uuid.UUID) -> None:
        collection = self._get_collection(project_id)
        collection.delete(ids=[str(memory_id)])

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Chroma metadata values must be str, int, float, or bool."""
        clean: Dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                clean[key] = value
            else:
                clean[key] = str(value)
        return clean


@lru_cache
def get_vector_store_service() -> VectorStoreService:
    return VectorStoreService()
