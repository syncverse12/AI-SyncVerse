from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel

from app.schemas.memory import MemoryOut


class WeeklySummaryResponse(BaseModel):
    project_id: UUID
    period_start: datetime
    period_end: datetime
    summary: str
    memories_considered: int
    highlighted_memories: List[MemoryOut]
