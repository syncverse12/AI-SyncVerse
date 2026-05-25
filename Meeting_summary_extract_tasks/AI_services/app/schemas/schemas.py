from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field, validator
import enum


# ── Auth ──────────────────────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8)
    department: Optional[str] = None
    role: Optional[str] = None


class EmployeeOut(BaseModel):
    id: str
    name: str
    email: str
    department: Optional[str]
    role: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


# ── Meeting ───────────────────────────────────────────────────────────────────

class MeetingCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    language: str = Field(default="en", pattern="^(en|ar|mixed)$")
    attendee_ids: List[str] = Field(default_factory=list)


class MeetingOut(BaseModel):
    id: str
    title: str
    host_id: str
    status: str
    language: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime
    attendees: List[EmployeeOut] = []

    class Config:
        from_attributes = True


class MeetingEndIn(BaseModel):
    meeting_id: str


# ── Transcript ────────────────────────────────────────────────────────────────

class UtteranceOut(BaseModel):
    speaker: str
    text: str
    start_ms: int
    end_ms: int
    language: str = "en"


class TranscriptOut(BaseModel):
    id: str
    meeting_id: str
    full_text_en: str
    full_text_ar: str
    utterances: List[dict]
    word_count: int
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Task ──────────────────────────────────────────────────────────────────────

class TaskOut(BaseModel):
    id: str
    meeting_id: str
    assignee_id: Optional[str]
    assignee_raw: Optional[str]
    title: str
    description: Optional[str]
    priority: str
    status: str
    deadline: Optional[datetime]
    estimated_hours: Optional[float]
    category: str
    source_quote: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskUpdateIn(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    deadline: Optional[datetime] = None
    description: Optional[str] = None


# ── Summary ───────────────────────────────────────────────────────────────────

class SummaryOut(BaseModel):
    id: str
    meeting_id: str
    overview: str
    key_points: List[str]
    decisions: List[str]
    blockers: List[str]
    next_steps: List[str]
    action_items: List[dict]
    full_markdown: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── WebSocket messages ────────────────────────────────────────────────────────

class WsEventType(str, enum.Enum):
    TRANSCRIPT_CHUNK = "transcript_chunk"
    TRANSLATION_CHUNK = "translation_chunk"
    TASK_EXTRACTED = "task_extracted"
    SUMMARY_READY = "summary_ready"
    MEETING_ENDED = "meeting_ended"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class WsMessage(BaseModel):
    event: WsEventType
    meeting_id: str
    payload: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)
