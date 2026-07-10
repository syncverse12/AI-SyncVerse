"""The Memory model: Echo's living, structured memory of everything that
happens across every team on a project."""
import enum
import uuid

from sqlalchemy import Enum as SAEnum, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class MemoryType(str, enum.Enum):
    decision = "decision"
    task = "task"
    meeting = "meeting"
    issue = "issue"
    requirement = "requirement"
    documentation = "documentation"
    risk = "risk"
    technical_discussion = "technical_discussion"
    architecture = "architecture"
    blocker = "blocker"


class Memory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single unit of project memory. Every memory is embedded and stored
    in ChromaDB (see VectorStoreService) so Echo can retrieve it semantically,
    regardless of which team or module produced it."""

    __tablename__ = "echo_memories"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    team_name: Mapped[str] = mapped_column(String(120), index=True, nullable=True)
    memory_type: Mapped[MemoryType] = mapped_column(
        SAEnum(MemoryType, name="memory_type_enum"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    # Populated once the embedding has been written to ChromaDB, so we can
    # detect and repair memories that failed to vectorize.
    embedding_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)

    def to_document_text(self) -> str:
        """Canonical text representation used for embedding generation."""
        parts = [f"[{self.memory_type.value.upper()}] {self.title}"]
        if self.team_name:
            parts.append(f"Team: {self.team_name}")
        if self.author:
            parts.append(f"Author: {self.author}")
        parts.append(self.content)
        return "\n".join(parts)
