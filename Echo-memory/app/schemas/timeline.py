from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel

from app.schemas.memory import MemoryOut


class TimelineResponse(BaseModel):
    project_id: UUID
    total: int
    items: List[MemoryOut]
