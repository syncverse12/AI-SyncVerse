"""
ai/factory.py
-------------
Provider Factory + automatic fallback + retry, all in one place so
enrichment.py never has to know which provider actually answered.
"""

from __future__ import annotations
from typing import List

from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.ai.base import BaseLLMProvider
from app.ai.groq_provider import GroqProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.huggingface_provider import HuggingFaceProvider
from app.config import get_settings
from app.core.exceptions import LLMProviderError, ProviderNotConfiguredError
from app.core.logging import get_logger, timed

logger = get_logger(__name__)

_REGISTRY = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "huggingface": HuggingFaceProvider,
}


def get_ordered_providers() -> List[BaseLLMProvider]:
    settings = get_settings()
    providers = [_REGISTRY[name]() for name in settings.LLM_PROVIDER_ORDER if name in _REGISTRY]
    configured = [p for p in providers if p.is_configured()]
    return configured


async def complete_with_fallback(system_prompt: str, user_prompt: str) -> tuple[str, str]:
    """Tries each configured provider in order, retrying each a few times
    before moving to the next. Returns (raw_text, provider_name_used)."""
    settings = get_settings()
    providers = get_ordered_providers()
    if not providers:
        raise ProviderNotConfiguredError(
            "No LLM provider is configured (set GROQ_API_KEY, GEMINI_API_KEY, "
            "or HUGGINGFACE_API_KEY) — AI enrichment will use deterministic defaults."
        )

    last_error: Exception | None = None
    for provider in providers:
        try:
            async for attempt in AsyncRetrying(
                reraise=True,
                stop=stop_after_attempt(settings.LLM_RETRY_ATTEMPTS),
                wait=wait_exponential(min=settings.LLM_RETRY_MIN_WAIT, max=settings.LLM_RETRY_MAX_WAIT),
                retry=retry_if_exception_type(LLMProviderError),
            ):
                with attempt:
                    with timed(logger, "llm_call", provider=provider.name):
                        text = await provider.complete(system_prompt, user_prompt)
                    return text, provider.name
        except LLMProviderError as exc:
            logger.warning(
                "LLM provider failed, trying next in fallback chain",
                extra={"provider": provider.name, "error": str(exc)},
            )
            last_error = exc
            continue

    raise LLMProviderError(f"All configured LLM providers failed. Last error: {last_error}")
