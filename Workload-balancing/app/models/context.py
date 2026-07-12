"""
models/context.py
------------------
WorkloadContext is the single internal representation everything downstream
of the Context Builder operates on. Nothing after this point — Metrics
Engine, AI Enrichment, Workload Engine, Report Builder — knows or cares
whether the data originated from the Backend API, Demo JSON, or was
subsequently AI-enriched. That's the whole point of this layer.
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.schemas import Employee, Task
from app.models.raw import RawTask, RawTeamSnapshot


class WorkloadContext(BaseModel):
    scope_type: str
    scope_id: str
    scope_name: str = ""
    source: str  # "backend" | "demo" — informational only, never branched on downstream

    employees: List[Employee]
    tasks: List[Task]

    # Kept around only so the AI Enrichment layer has rich text (titles,
    # descriptions, categories) to reason over — the deterministic engine
    # never touches this.
    raw_tasks_by_employee: dict[str, List[RawTask]] = Field(default_factory=dict)

    data_quality_warnings: List[str] = Field(default_factory=list)
