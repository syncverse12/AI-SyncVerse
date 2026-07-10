"""Documentation Mode: generates API documentation, architecture summaries,
sprint reports, and onboarding material from accumulated project memory."""
import uuid
from typing import List

from sqlalchemy.orm import Session

from app.models.memory import Memory, MemoryType
from app.repositories.memory_repository import MemoryRepository


class DocumentationService:
    def __init__(self, db: Session):
        self.db = db
        self.memory_repo = MemoryRepository(db)

    def build_context(self, project_id: uuid.UUID, message: str) -> str:
        """Assembles the most relevant structured memories (architecture,
        decisions, documentation) as grounding context for documentation
        generation, since these requests benefit from broad recall rather
        than a narrow semantic top-k."""
        relevant_types = [
            MemoryType.architecture,
            MemoryType.decision,
            MemoryType.documentation,
            MemoryType.technical_discussion,
            MemoryType.requirement,
        ]

        chunks: List[str] = []
        for mt in relevant_types:
            memories = self.memory_repo.get_by_type(project_id, mt, limit=15)
            if not memories:
                continue
            chunks.append(f"--- {mt.value.upper()} MEMORIES ---")
            for m in memories:
                chunks.append(f"* {m.title} (team: {m.team_name or 'n/a'}): {m.content[:400]}")

        return "\n".join(chunks) if chunks else "No architecture, decision, or documentation memories recorded yet."
