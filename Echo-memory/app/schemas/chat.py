from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EchoChatRequest(BaseModel):
    project_id: UUID
    user_id: str
    message: str = Field(..., min_length=1)


class SourceMemory(BaseModel):
    memory_id: UUID
    title: str
    memory_type: str
    team_name: Optional[str] = None
    relevance_score: float


class EchoChatResponse(BaseModel):
    response: str
    sources: List[SourceMemory] = Field(default_factory=list)
    mode: str
    confidence: float


class ConversationMessageOut(BaseModel):
    role: str
    content: str
    mode: Optional[str] = None
