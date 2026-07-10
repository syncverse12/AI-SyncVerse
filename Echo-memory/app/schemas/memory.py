from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.memory import MemoryType
from app.schemas.common import ORMModel


class MemoryCreate(BaseModel):
    project_id: UUID
    team_name: Optional[str] = None
    memory_type: MemoryType
    title: str = Field(..., max_length=500)
    content: str
    author: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryOut(ORMModel):
    id: UUID
    project_id: UUID
    team_name: Optional[str] = None
    memory_type: MemoryType
    title: str
    content: str
    author: Optional[str] = None
    created_at: datetime


class MemorySearchResult(BaseModel):
    memory: MemoryOut
    relevance_score: float
