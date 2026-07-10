"""Orchestrates writing memories to PostgreSQL (source of truth) and
ChromaDB (semantic index), and retrieving them semantically."""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.memory import Memory, MemoryType
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryCreate, MemorySearchResult, MemoryOut
from app.services.vector_store_service import VectorStoreService, get_vector_store_service

logger = get_logger(__name__)


class MemoryService:
    def __init__(self, db: Session, vector_store: Optional[VectorStoreService] = None):
        self.db = db
        self.repo = MemoryRepository(db)
        self.vector_store = vector_store or get_vector_store_service()

    def create_memory(self, payload: MemoryCreate) -> Memory:
        memory = Memory(
            project_id=payload.project_id,
            team_name=payload.team_name,
            memory_type=payload.memory_type,
            title=payload.title,
            content=payload.content,
            author=payload.author,
            metadata_json=payload.metadata or {},
        )
        memory = self.repo.create(memory)

        try:
            doc_id = self.vector_store.upsert_memory(
                memory_id=memory.id,
                project_id=memory.project_id,
                document_text=memory.to_document_text(),
                metadata={
                    "memory_id": str(memory.id),
                    "team_name": memory.team_name,
                    "memory_type": memory.memory_type.value,
                    "title": memory.title,
                    "author": memory.author,
                    "created_at": memory.created_at.isoformat(),
                },
            )
            memory.embedding_id = doc_id
            self.db.commit()
            self.db.refresh(memory)
        except Exception as exc:  # pragma: no cover - defensive
            # The memory is still safely persisted in Postgres even if
            # embedding generation fails; it can be re-indexed later.
            logger.error("Failed to embed memory %s: %s", memory.id, exc)

        logger.info(
            "Memory recorded [%s] project=%s team=%s title=%r",
            memory.memory_type.value, memory.project_id, memory.team_name, memory.title,
        )
        return memory

    def semantic_search(
        self,
        project_id: uuid.UUID,
        query: str,
        top_k: int = 8,
        team_name: Optional[str] = None,
        memory_type: Optional[str] = None,
    ) -> List[MemorySearchResult]:
        raw_results = self.vector_store.query(
            project_id=project_id,
            query_text=query,
            top_k=top_k,
            team_name=team_name,
            memory_type=memory_type,
        )
        if not raw_results:
            return []

        ids = [uuid.UUID(r["id"]) for r in raw_results]
        memories_by_id = {m.id: m for m in self.repo.get_by_ids(ids)}

        results: List[MemorySearchResult] = []
        for r in raw_results:
            memory = memories_by_id.get(uuid.UUID(r["id"]))
            if memory is None:
                continue
            results.append(
                MemorySearchResult(
                    memory=MemoryOut.model_validate(memory),
                    relevance_score=round(r["score"], 4),
                )
            )
        return results

    def get_timeline(
        self,
        project_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
        memory_type: Optional[MemoryType] = None,
        team_name: Optional[str] = None,
    ) -> List[Memory]:
        return self.repo.get_timeline(
            project_id, limit=limit, offset=offset, memory_type=memory_type, team_name=team_name
        )

    def get_since(self, project_id: uuid.UUID, since: datetime) -> List[Memory]:
        return self.repo.get_since(project_id, since)
