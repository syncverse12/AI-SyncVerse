from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ── Request ───────────────────────────────────────────────────────────────────

class TaskExtractionRequest(BaseModel):
    meeting_id: int | str = Field(..., description="Unique meeting identifier")
    transcript: str = Field(
        ...,
        min_length=10,
        description="Full meeting transcript text (English or Arabic)",
    )
    attendees: list[str] = Field(
        default_factory=list,
        description="List of known attendee names for better assignee resolution",
    )
    meeting_date: Optional[str] = Field(
        default=None,
        description="Meeting date in YYYY-MM-DD format; used to resolve relative deadlines",
    )


# ── Task item ─────────────────────────────────────────────────────────────────

class ExtractedTask(BaseModel):
    title: str = Field(..., description="Short actionable task title")
    description: Optional[str] = Field(None, description="Additional context")
    assignee: Optional[str] = Field(None, description="Name of the responsible person")
    deadline: Optional[str] = Field(None, description="Deadline in YYYY-MM-DD or null")
    priority: str = Field(default="MEDIUM", description="URGENT | HIGH | MEDIUM | LOW")
    category: str = Field(default="general", description="Task category")
    estimated_hours: Optional[float] = Field(None, description="Estimated effort in hours")
    source_quote: Optional[str] = Field(None, description="Verbatim text that triggered this task")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Extraction confidence score")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        mapping = {"U": "URGENT", "H": "HIGH", "M": "MEDIUM", "L": "LOW"}
        upper = v.strip().upper()
        return mapping.get(upper[0], upper) if upper else "MEDIUM"

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {
            "development", "design", "testing", "meeting",
            "documentation", "deployment", "general", "research",
        }
        return v.lower() if v.lower() in allowed else "general"


# ── Response ──────────────────────────────────────────────────────────────────

class TaskExtractionResponse(BaseModel):
    meeting_id: int | str
    tasks: list[ExtractedTask]
    tasks_count: int
    processing_notes: list[str] = Field(default_factory=list)


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str
    version: str
