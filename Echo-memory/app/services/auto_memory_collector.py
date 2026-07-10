"""Automatic Memory Collection.

Other parts of the SyncVerse platform (task boards, requirements module,
risk register, sprint planner, meeting notes, architecture decisions) call
these helpers whenever something noteworthy happens, so project memory
builds itself instead of requiring manual data entry.

Each function is intentionally a thin, explicit wrapper around
MemoryService.create_memory so the mapping from "platform event" to
"memory" stays obvious and easy to extend.
"""
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.memory import MemoryType
from app.schemas.memory import MemoryCreate
from app.services.memory_service import MemoryService


class AutoMemoryCollector:
    def __init__(self, db: Session):
        self.memory_service = MemoryService(db)

    def task_completed(
        self,
        project_id: uuid.UUID,
        team_name: str,
        task_title: str,
        completed_by: str,
        details: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        return self.memory_service.create_memory(
            MemoryCreate(
                project_id=project_id,
                team_name=team_name,
                memory_type=MemoryType.task,
                title=f"Task completed: {task_title}",
                content=details or f"{task_title} was marked complete by {completed_by}.",
                author=completed_by,
                metadata=metadata or {"event": "task_completed"},
            )
        )

    def requirement_changed(
        self,
        project_id: uuid.UUID,
        requirement_title: str,
        change_description: str,
        changed_by: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        return self.memory_service.create_memory(
            MemoryCreate(
                project_id=project_id,
                team_name=None,
                memory_type=MemoryType.requirement,
                title=f"Requirement changed: {requirement_title}",
                content=change_description,
                author=changed_by,
                metadata=metadata or {"event": "requirement_changed"},
            )
        )

    def risk_added(
        self,
        project_id: uuid.UUID,
        team_name: Optional[str],
        risk_title: str,
        description: str,
        severity: str,
        reported_by: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        return self.memory_service.create_memory(
            MemoryCreate(
                project_id=project_id,
                team_name=team_name,
                memory_type=MemoryType.risk,
                title=f"Risk added: {risk_title} ({severity})",
                content=description,
                author=reported_by,
                metadata=metadata or {"event": "risk_added", "severity": severity},
            )
        )

    def sprint_started(
        self,
        project_id: uuid.UUID,
        sprint_name: str,
        goals: str,
        started_by: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        return self.memory_service.create_memory(
            MemoryCreate(
                project_id=project_id,
                team_name=None,
                memory_type=MemoryType.meeting,
                title=f"Sprint started: {sprint_name}",
                content=goals,
                author=started_by,
                metadata=metadata or {"event": "sprint_started"},
            )
        )

    def meeting_summary_generated(
        self,
        project_id: uuid.UUID,
        team_name: Optional[str],
        meeting_title: str,
        summary: str,
        attendees: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        return self.memory_service.create_memory(
            MemoryCreate(
                project_id=project_id,
                team_name=team_name,
                memory_type=MemoryType.meeting,
                title=meeting_title,
                content=f"{summary}\n\nAttendees: {attendees}" if attendees else summary,
                author=None,
                metadata=metadata or {"event": "meeting_summary"},
            )
        )

    def technical_decision_created(
        self,
        project_id: uuid.UUID,
        team_name: Optional[str],
        decision_title: str,
        decision: str,
        rationale: str,
        decided_by: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        content = f"Decision: {decision}\n\nRationale: {rationale}"
        return self.memory_service.create_memory(
            MemoryCreate(
                project_id=project_id,
                team_name=team_name,
                memory_type=MemoryType.decision,
                title=decision_title,
                content=content,
                author=decided_by,
                metadata=metadata or {"event": "technical_decision"},
            )
        )

    def blocker_reported(
        self,
        project_id: uuid.UUID,
        team_name: str,
        blocked_on_team: str,
        description: str,
        reported_by: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        meta = metadata or {}
        meta.update({"event": "blocker_reported", "blocked_on_team": blocked_on_team})
        return self.memory_service.create_memory(
            MemoryCreate(
                project_id=project_id,
                team_name=team_name,
                memory_type=MemoryType.blocker,
                title=f"Blocker: {team_name} blocked on {blocked_on_team}",
                content=description,
                author=reported_by,
                metadata=meta,
            )
        )
