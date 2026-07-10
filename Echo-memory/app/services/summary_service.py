"""Generates weekly (or arbitrary-period) project summaries from recorded
memories, e.g. for GET /echo/summary/week."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.repositories.memory_repository import MemoryRepository
from app.services.llm_service import LLMService, get_llm_service


class SummaryService:
    def __init__(self, db: Session, llm_service: LLMService = None):
        self.db = db
        self.memory_repo = MemoryRepository(db)
        self.llm_service = llm_service or get_llm_service()

    def generate_weekly_summary(
        self, project_id: uuid.UUID
    ) -> tuple[str, List[Memory], datetime, datetime, int]:
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(days=7)

        memories = self.memory_repo.get_since(project_id, period_start)

        if not memories:
            return (
                "No project activity was recorded this week.",
                [],
                period_start,
                period_end,
                0,
            )

        grouped = self._group_by_type(memories)
        context_lines = []
        for memory_type, items in grouped.items():
            context_lines.append(f"\n{memory_type.upper()} ({len(items)}):")
            for m in items:
                context_lines.append(f"- [{m.team_name or 'n/a'}] {m.title}: {m.content[:250]}")
        context = "\n".join(context_lines)

        system_prompt = (
            "You are Echo, the AI teammate and living memory of a software "
            "project. Write a concise, well-organized weekly summary of "
            "everything that happened, grouped by theme (decisions, "
            "progress, risks/blockers, meetings). Use plain prose with short "
            "bullet points. Be factual and specific, referencing team names "
            "where relevant. Do not invent information not present in the "
            "provided memories."
        )
        user_prompt = f"Here are this week's project memories:\n{context}\n\nWrite the weekly summary."

        summary_text = self.llm_service.generate(system_prompt, user_prompt)

        # Highlight the most significant memories (decisions, risks, blockers first).
        priority_types = {"decision", "risk", "blocker", "architecture"}
        highlighted = sorted(
            memories,
            key=lambda m: (m.memory_type.value not in priority_types, m.created_at),
            reverse=False,
        )[:10]

        return summary_text, highlighted, period_start, period_end, len(memories)

    @staticmethod
    def _group_by_type(memories: List[Memory]) -> dict:
        grouped: dict = {}
        for m in memories:
            grouped.setdefault(m.memory_type.value, []).append(m)
        return grouped
