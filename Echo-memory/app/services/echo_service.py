"""EchoService is the orchestration layer behind POST /echo/chat.

For every incoming message it:
  1. Loads recent conversation history (per project + per user).
  2. Classifies the message into one of Echo's four modes.
  3. Retrieves relevant grounding context (semantic memory search, and/or
     structured coordination/documentation context depending on mode).
  4. Builds a mode-specific system prompt and calls the LLM.
  5. Persists both the user's message and Echo's reply to conversation
     history, and returns sources + a confidence score.
"""
import uuid
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.conversation import MessageRole
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chat import EchoChatResponse, SourceMemory
from app.schemas.memory import MemorySearchResult
from app.services.documentation_service import DocumentationService
from app.services.llm_service import LLMService, get_llm_service
from app.services.memory_service import MemoryService
from app.services.mode_classifier import EchoMode, ModeClassifier
from app.services.project_manager_service import ProjectManagerService

logger = get_logger(__name__)


_MODE_SYSTEM_PROMPTS = {
    EchoMode.memory: (
        "You are Echo, the living memory of this software project. You "
        "remember every decision, task, meeting, and discussion across all "
        "teams (Frontend, Backend, AI, UI/UX, Security, DevOps, etc). "
        "Answer the question using ONLY the project memories provided as "
        "context below. If the memories don't contain the answer, say so "
        "honestly rather than guessing. Speak as a knowledgeable teammate, "
        "not a generic assistant - be specific about who, what, and why."
    ),
    EchoMode.technical_advisor: (
        "You are Echo, acting as a senior technical advisor embedded in "
        "this project. Combine the project's own architecture and past "
        "decisions (given as context) with general software engineering "
        "best practices to give a clear, opinionated recommendation. "
        "Explicitly reference the project's existing stack and constraints "
        "when relevant, and briefly justify trade-offs."
    ),
    EchoMode.project_manager: (
        "You are Echo, acting as an attentive project coordinator who "
        "tracks blockers, dependencies, and cross-team status. Use the "
        "structured coordination context and memories below to answer "
        "clearly and concretely - name the teams and tasks involved. If "
        "asked for the current status, be direct about what's blocked and "
        "on whom."
    ),
    EchoMode.documentation: (
        "You are Echo, acting as a technical writer with full knowledge of "
        "this project's architecture, decisions, and requirements. Generate "
        "clear, well-structured documentation (using headings and bullet "
        "points where useful) strictly grounded in the context provided "
        "below. Do not invent APIs, decisions, or facts not present in the "
        "context."
    ),
}


class EchoService:
    def __init__(self, db: Session, llm_service: LLMService = None):
        self.db = db
        self.memory_service = MemoryService(db)
        self.conversation_repo = ConversationRepository(db)
        self.llm_service = llm_service or get_llm_service()
        self.mode_classifier = ModeClassifier(self.llm_service)
        self.project_manager_service = ProjectManagerService(db)
        self.documentation_service = DocumentationService(db)

    def chat(self, project_id: uuid.UUID, user_id: str, message: str) -> EchoChatResponse:
        mode = self.mode_classifier.classify(message)
        logger.info("Echo classified message as mode=%s (project=%s)", mode.value, project_id)

        search_results = self.memory_service.semantic_search(
            project_id=project_id,
            query=message,
            top_k=settings.ECHO_MAX_CONTEXT_MEMORIES,
        )

        context = self._build_context(project_id, mode, message, search_results)
        history = self._load_history(project_id, user_id)

        system_prompt = _MODE_SYSTEM_PROMPTS[mode]
        user_prompt = (
            f"CONTEXT:\n{context}\n\n"
            f"USER QUESTION:\n{message}\n\n"
            "Answer the question directly and helpfully."
        )

        answer = self.llm_service.generate(system_prompt, user_prompt, history=history)
        confidence = self._estimate_confidence(mode, search_results)

        sources = [
            SourceMemory(
                memory_id=r.memory.id,
                title=r.memory.title,
                memory_type=r.memory.memory_type.value,
                team_name=r.memory.team_name,
                relevance_score=r.relevance_score,
            )
            for r in search_results
        ]

        self.conversation_repo.add_message(project_id, user_id, MessageRole.user, message)
        self.conversation_repo.add_message(
            project_id, user_id, MessageRole.echo, answer, mode=mode.value
        )

        return EchoChatResponse(response=answer, sources=sources, mode=mode.value, confidence=confidence)

    def _build_context(
        self,
        project_id: uuid.UUID,
        mode: EchoMode,
        message: str,
        search_results: List[MemorySearchResult],
    ) -> str:
        memory_context = self._format_memory_results(search_results)

        if mode == EchoMode.project_manager:
            structured = self.project_manager_service.build_context(project_id)
            return f"{structured}\n\nRelated memories:\n{memory_context}"

        if mode == EchoMode.documentation:
            structured = self.documentation_service.build_context(project_id, message)
            return f"{structured}\n\nAdditional related memories:\n{memory_context}"

        # memory + technical_advisor modes rely primarily on semantic search
        return memory_context

    @staticmethod
    def _format_memory_results(results: List[MemorySearchResult]) -> str:
        if not results:
            return "No relevant project memories were found for this question."
        lines = []
        for r in results:
            m = r.memory
            lines.append(
                f"- ({m.memory_type.value}, team: {m.team_name or 'n/a'}, "
                f"relevance: {r.relevance_score}) {m.title}: {m.content[:400]}"
            )
        return "\n".join(lines)

    def _load_history(self, project_id: uuid.UUID, user_id: str) -> List[Tuple[str, str]]:
        messages = self.conversation_repo.get_recent(
            project_id, user_id, limit=settings.ECHO_CONVERSATION_HISTORY_LIMIT
        )
        history: List[Tuple[str, str]] = []
        for msg in messages:
            role = "user" if msg.role == MessageRole.user else "assistant"
            history.append((role, msg.content))
        return history

    @staticmethod
    def _estimate_confidence(mode: EchoMode, search_results: List[MemorySearchResult]) -> float:
        if mode in (EchoMode.project_manager, EchoMode.documentation):
            # These modes lean on structured data as well as memory, so a
            # thin semantic result set is less disqualifying.
            base = 0.6
        else:
            base = 0.3

        if not search_results:
            return round(max(settings.ECHO_MIN_CONFIDENCE, base - 0.15), 2)

        top_score = search_results[0].relevance_score
        avg_score = sum(r.relevance_score for r in search_results) / len(search_results)
        confidence = base + 0.5 * top_score + 0.2 * avg_score
        return round(min(0.98, max(settings.ECHO_MIN_CONFIDENCE, confidence)), 2)
