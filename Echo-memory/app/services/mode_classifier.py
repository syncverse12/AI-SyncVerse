"""Determines which of Echo's four intelligence modes should answer a given
message: memory, technical_advisor, project_manager, or documentation.

Uses fast keyword heuristics first (cheap, deterministic, no API call) and
only falls back to the LLM for genuinely ambiguous phrasing.
"""
import enum
import re
from typing import Optional

from app.core.logging_config import get_logger
from app.services.llm_service import LLMService

logger = get_logger(__name__)


class EchoMode(str, enum.Enum):
    memory = "memory"
    technical_advisor = "technical_advisor"
    project_manager = "project_manager"
    documentation = "documentation"


_DOCUMENTATION_PATTERNS = [
    r"\bgenerate (api )?doc", r"\bwrite documentation", r"\bdocument the\b",
    r"\bonboarding (doc|guide)", r"\bsprint report\b", r"\barchitecture summary\b",
    r"\bproduce documentation\b",
]

_PROJECT_MANAGER_PATTERNS = [
    r"\bblocker", r"\bdependenc", r"\bdelayed\b", r"\bbehind schedule\b",
    r"\bwho (is|are) waiting on\b", r"\bcoordinat", r"\bwhich teams? depend\b",
    r"\bstatus of the sprint\b", r"\bwhat.?s (blocking|slowing)\b",
]

_TECHNICAL_ADVISOR_PATTERNS = [
    r"\bshould we\b", r"\bwhich is better\b", r"\bwebsockets? or\b", r"\brecommend",
    r"\bbest practice", r"\bhow should (we|i) implement\b", r"\bwhat.?s the best way\b",
    r"\bpros and cons\b", r"\btrade-?offs?\b",
]

_MEMORY_PATTERNS = [
    r"\bwhy did we (choose|pick|use|decide)\b", r"\bwho (implemented|built|wrote|worked on)\b",
    r"\bwhat decisions? (was|were) made\b", r"\bsummar", r"\bwhat is our\b",
    r"\bwhat happened\b",
]


class ModeClassifier:
    def __init__(self, llm_service: LLMService) -> None:
        self._llm_service = llm_service

    def classify(self, message: str) -> EchoMode:
        text = message.lower().strip()

        if self._matches_any(text, _DOCUMENTATION_PATTERNS):
            return EchoMode.documentation
        if self._matches_any(text, _PROJECT_MANAGER_PATTERNS):
            return EchoMode.project_manager
        if self._matches_any(text, _TECHNICAL_ADVISOR_PATTERNS):
            return EchoMode.technical_advisor
        if self._matches_any(text, _MEMORY_PATTERNS):
            return EchoMode.memory

        # Ambiguous: ask the LLM to pick, falling back to memory mode (the
        # safest default - it still grounds the answer in project context).
        return self._classify_with_llm(message) or EchoMode.memory

    @staticmethod
    def _matches_any(text: str, patterns: list[str]) -> bool:
        return any(re.search(p, text) for p in patterns)

    def _classify_with_llm(self, message: str) -> Optional[EchoMode]:
        if not self._llm_service.is_configured:
            return None
        system_prompt = (
            "Classify the user's message into exactly one of these labels: "
            "memory, technical_advisor, project_manager, documentation. "
            "Respond with only the single label word, nothing else."
        )
        try:
            raw = self._llm_service.generate(system_prompt, message).strip().lower()
            for mode in EchoMode:
                if mode.value in raw:
                    return mode
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("LLM mode classification failed: %s", exc)
        return None
