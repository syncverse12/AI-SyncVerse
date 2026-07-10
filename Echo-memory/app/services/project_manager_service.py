"""Project Manager Mode: analyzes blockers, dependencies, delayed tasks,
and cross-team coordination issues, combining structured data (tasks,
risks) with relevant memories (blockers, issues)."""
import uuid
from typing import List

from sqlalchemy.orm import Session

from app.models.memory import MemoryType
from app.models.task import TaskStatus
from app.repositories.memory_repository import MemoryRepository
from app.repositories.risk_repository import RiskRepository
from app.repositories.task_repository import TaskRepository


class ProjectManagerService:
    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepository(db)
        self.risk_repo = RiskRepository(db)
        self.memory_repo = MemoryRepository(db)

    def build_context(self, project_id: uuid.UUID) -> str:
        """Builds a structured context block summarizing current
        coordination state, to be handed to the LLM alongside retrieved
        memories."""
        blocked_tasks = self.task_repo.get_blocked(project_id)
        high_risks = self.risk_repo.get_high_severity(project_id)
        blocker_memories = self.memory_repo.get_by_type(project_id, MemoryType.blocker, limit=20)

        lines: List[str] = []

        if blocked_tasks:
            lines.append("Currently blocked tasks:")
            for t in blocked_tasks:
                lines.append(
                    f"- '{t.title}' (team: {t.team_name or 'unknown'}, "
                    f"assignee: {t.assignee or 'unassigned'}, "
                    f"depends on: {t.depends_on_team or 'n/a'})"
                )
        else:
            lines.append("No tasks are currently marked as blocked.")

        if high_risks:
            lines.append("\nHigh/critical severity risks:")
            for r in high_risks:
                lines.append(f"- '{r.title}' (severity: {r.severity.value}, team: {r.team_name or 'n/a'})")

        if blocker_memories:
            lines.append("\nRecently reported blockers (from project memory):")
            for m in blocker_memories[:10]:
                lines.append(f"- [{m.team_name or 'n/a'}] {m.title}: {m.content[:200]}")

        return "\n".join(lines) if lines else "No coordination data available yet for this project."
