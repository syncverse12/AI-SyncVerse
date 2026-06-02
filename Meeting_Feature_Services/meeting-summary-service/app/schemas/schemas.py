from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ── Request ───────────────────────────────────────────────────────────────────

class SummaryRequest(BaseModel):
    meeting_id: int | str = Field(..., description="Unique meeting identifier")
    transcript: str = Field(
        ...,
        min_length=10,
        description="Full meeting transcript text",
    )
    meeting_title: str = Field(
        default="Team Meeting",
        description="Title of the meeting",
    )
    attendees: list[str] = Field(
        default_factory=list,
        description="List of attendee names",
    )
    language: str = Field(
        default="en",
        description="Output language: 'en' for English, 'ar' for Arabic",
        pattern="^(en|ar)$",
    )


# ── Action item ───────────────────────────────────────────────────────────────

class ActionItem(BaseModel):
    task: str
    owner: Optional[str] = None
    deadline: Optional[str] = None


# ── Response ──────────────────────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    meeting_id: int | str
    meeting_title: str
    summary: str = Field(..., description="Concise 2-4 sentence executive overview")
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    full_markdown: Optional[str] = Field(None, description="Complete markdown-formatted summary")


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str
    version: str
