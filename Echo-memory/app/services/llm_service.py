"""Chat-completion layer used by every Echo mode (memory, technical advisor,
project manager, documentation).

Provider strategy
------------------
- Primary provider: Groq (fast Llama-family models via LangChain's
  ``ChatGroq``).
- Fallback provider: Google Gemini (``ChatGoogleGenerativeAI``), used
  automatically whenever the Groq call fails for a retryable reason
  (timeout, rate limit / 429, quota exhaustion, transient 5xx, or a
  network error).
- ``CHAT_PROVIDER`` (env var) can force a single provider ("groq" or
  "gemini") for environments that only have one key configured.

The retrieval pipeline (ChromaDB, embeddings, prompt construction) is
untouched - this module only changes *which model* answers the already
-built prompt, and only exposes the same ``generate`` / ``is_configured``
interface the rest of the app already depends on.
"""
from functools import lru_cache
from typing import List, Optional, Tuple

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Substrings that identify a retryable failure (timeout, rate limit, quota,
# transient network/server error). Anything matching here triggers an
# automatic fallback to the secondary provider.
_RETRYABLE_MARKERS = (
    "timeout",
    "timed out",
    "rate limit",
    "rate_limit",
    "ratelimit",
    "429",
    "resourceexhausted",
    "resource_exhausted",
    "quota",
    "503",
    "502",
    "500",
    "service unavailable",
    "unavailable",
    "connection",
    "connect timeout",
    "network",
    "temporarily",
)


def _is_retryable_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _RETRYABLE_MARKERS)


def _is_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "resourceexhausted" in text or "429" in text or "quota" in text


class LLMService:
    """Wraps the chat model(s) behind the same small interface Echo has
    always used (``generate`` / ``is_configured``). Clients are created once
    in ``__init__`` - and this class itself is served as a process-wide
    singleton via ``get_llm_service`` - so no new HTTP client is created per
    request.
    """

    def __init__(self) -> None:
        self._groq_client = None
        self._gemini_client = None

        provider = settings.chat_provider_normalized  # "groq" | "gemini"
        self._provider_preference = provider

        if provider != "gemini" and settings.has_groq_credentials:
            self._groq_client = self._build_groq_client()

        if provider != "groq" or self._groq_client is None:
            if settings.has_llm_credentials:
                self._gemini_client = self._build_gemini_client()

        # If Groq is the active primary, keep a warm Gemini client around as
        # the automatic fallback even though Groq handles requests normally.
        if (
            provider == "groq"
            and self._groq_client is not None
            and self._gemini_client is None
            and settings.has_llm_credentials
        ):
            self._gemini_client = self._build_gemini_client()

        if self._groq_client is None and self._gemini_client is None:
            logger.warning(
                "No chat provider credentials configured (GROQ_API_KEY / "
                "GOOGLE_API_KEY) - LLMService will return a placeholder "
                "response until at least one is set."
            )

    # ------------------------------------------------------------------
    # Client construction (each called at most once per process)
    # ------------------------------------------------------------------
    def _build_groq_client(self):
        try:
            from langchain_groq import ChatGroq

            client = ChatGroq(
                model=settings.GROQ_CHAT_MODEL,
                api_key=settings.GROQ_API_KEY,
                temperature=0.3,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
                max_retries=settings.LLM_MAX_RETRIES,
            )
            logger.info(
                "Groq chat client initialized (model=%s)",
                settings.GROQ_CHAT_MODEL,
            )
            return client
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to initialize Groq chat client: %s", exc)
            return None

    def _build_gemini_client(self):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            client = ChatGoogleGenerativeAI(
                model=settings.GEMINI_CHAT_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.3,
                # Gemini's SDK auto-retries on 429s with growing backoff (up
                # to ~20-50s per attempt by default). Fail fast here so the
                # *outer* fallback logic in `generate()` stays in control of
                # retry behaviour instead of hanging inside the SDK.
                max_retries=settings.LLM_MAX_RETRIES,
            )
            logger.info(
                "Gemini chat client initialized (model=%s)",
                settings.GEMINI_CHAT_MODEL,
            )
            return client
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to initialize Gemini chat client: %s", exc)
            return None

    @property
    def is_configured(self) -> bool:
        return self._groq_client is not None or self._gemini_client is not None

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Tuple[str, str]]] = None,
    ) -> str:
        """history: list of (role, content) tuples, role in {"user", "assistant"}."""
        if self._groq_client is None and self._gemini_client is None:
            return (
                "Echo is not fully configured yet - a GROQ_API_KEY or "
                "GOOGLE_API_KEY is required to generate answers. Once "
                "configured, I'll be able to reason over this project's "
                "memory and answer this question."
            )

        messages = self._build_messages(system_prompt, user_prompt, history)

        if self._groq_client is not None:
            try:
                result = self._groq_client.invoke(messages)
                logger.info(
                    "Chat request handled by provider=groq model=%s fallback=false",
                    settings.GROQ_CHAT_MODEL,
                )
                return self._extract_content(result)
            except Exception as exc:
                if self._gemini_client is not None:
                    reason = "retryable" if _is_retryable_error(exc) else "non-retryable, fallback available"
                    logger.warning(
                        "Groq chat call failed (%s: %s) - falling back to Gemini for this request.",
                        reason,
                        exc,
                    )
                    return self._generate_with_gemini(messages, fallback=True)
                logger.error("Groq chat call failed and no fallback configured: %s", exc)
                return self._error_response(exc, provider="groq")

        # Groq not configured at all - Gemini is the only/primary provider.
        return self._generate_with_gemini(messages, fallback=False)

    def _generate_with_gemini(self, messages, fallback: bool) -> str:
        try:
            result = self._gemini_client.invoke(messages)
            logger.info(
                "Chat request handled by provider=gemini model=%s fallback=%s",
                settings.GEMINI_CHAT_MODEL,
                str(fallback).lower(),
            )
            return self._extract_content(result)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "Gemini chat call failed%s: %s",
                " (fallback attempt)" if fallback else "",
                exc,
            )
            return self._error_response(exc, provider="gemini")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_messages(
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Tuple[str, str]]],
    ):
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        messages = [SystemMessage(content=system_prompt)]
        for role, content in history or []:
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=user_prompt))
        return messages

    @staticmethod
    def _extract_content(result) -> str:
        return result.content if hasattr(result, "content") else str(result)

    @staticmethod
    def _error_response(exc: Exception, provider: str) -> str:
        if _is_quota_error(exc):
            if provider == "gemini":
                return (
                    "Echo can't reach Gemini right now because the "
                    "configured API key has no available quota for this "
                    f"model ({settings.GEMINI_CHAT_MODEL}). Check "
                    "https://aistudio.google.com/rate-limit for your "
                    "project's live limits, or switch GEMINI_CHAT_MODEL to "
                    "a model with free quota available."
                )
            return (
                "Echo can't reach Groq right now because the configured "
                "API key has no available quota or rate limit remaining "
                f"for this model ({settings.GROQ_CHAT_MODEL}). Check "
                "https://console.groq.com/settings/limits, or configure "
                "GOOGLE_API_KEY so Echo can automatically fall back to "
                "Gemini."
            )
        return (
            "I ran into an issue reaching the language model just now. "
            "Please try again in a moment."
        )


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService()
