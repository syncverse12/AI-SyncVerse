"""
app/schemas/requests.py  &  app/schemas/responses.py  (combined)
API-level Pydantic schemas for request validation and response serialisation.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel

from app.models.domain import (
    AlignmentScoreResult,
    AIJudgeResult,
    HealthScoreResult,
    Project,
    Task,
    Requirement,
    Deliverable,
    ProjectNote,
)


# ─── Request bodies ──────────────────────────────────────────────────────────

class UpsertProjectRequest(BaseModel):
    project: Project


class UpsertTaskRequest(BaseModel):
    task: Task


class UpsertRequirementRequest(BaseModel):
    requirement: Requirement


class UpsertDeliverableRequest(BaseModel):
    deliverable: Deliverable


class UpsertNoteRequest(BaseModel):
    note: ProjectNote


# ─── Evaluation response wrappers ────────────────────────────────────────────

class HealthResponse(BaseModel):
    success: bool = True
    data: HealthScoreResult


class AlignmentResponse(BaseModel):
    success: bool = True
    data: AlignmentScoreResult


class AIJudgeResponse(BaseModel):
    success: bool = True
    data: AIJudgeResult


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
