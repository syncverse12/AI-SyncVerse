import uuid
from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import Memory, MemoryType
from app.repositories.base import BaseRepository


class MemoryRepository(BaseRepository[Memory]):
    def __init__(self, db: Session):
        super().__init__(db, Memory)

    def get_timeline(
        self,
        project_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
        memory_type: Optional[MemoryType] = None,
        team_name: Optional[str] = None,
    ) -> List[Memory]:
        stmt = select(Memory).where(Memory.project_id == project_id)
        if memory_type is not None:
            stmt = stmt.where(Memory.memory_type == memory_type)
        if team_name is not None:
            stmt = stmt.where(Memory.team_name == team_name)
        stmt = stmt.order_by(Memory.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars().all())

    def get_since(self, project_id: uuid.UUID, since: datetime) -> List[Memory]:
        stmt = (
            select(Memory)
            .where(Memory.project_id == project_id, Memory.created_at >= since)
            .order_by(Memory.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_ids(self, ids: Sequence[uuid.UUID]) -> List[Memory]:
        if not ids:
            return []
        stmt = select(Memory).where(Memory.id.in_(list(ids)))
        return list(self.db.execute(stmt).scalars().all())

    def get_by_type(self, project_id: uuid.UUID, memory_type: MemoryType, limit: int = 200) -> List[Memory]:
        stmt = (
            select(Memory)
            .where(Memory.project_id == project_id, Memory.memory_type == memory_type)
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
