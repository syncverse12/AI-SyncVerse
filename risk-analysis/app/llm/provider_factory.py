"""
Tries LLM providers in the configured order (settings.llm_provider_order,
default "gemini,groq") and falls back automatically on any
LLMProviderUnavailableError — this is the Gemini-429 -> Groq fallback
pattern proven in the sibling Risk Forecasting service, generalized to N
providers via tenacity-free simple sequential fallback (retries within a
single provider are the provider's own concern if needed; cross-provider
fallback is intentionally immediate, not retried, to fail over fast).
"""

import logging
from typing import List
from app.core.config import get_settings
from app.llm.base import LLMProvider
from app.llm.providers.gemini import GeminiProvider
from app.llm.providers.groq import GroqProvider
from app.llm.providers.huggingface import HuggingFaceProvider
from app.exceptions.llm import LLMProviderUnavailableError, AllLLMProvidersExhaustedError
from app.core.logging_config import log_duration

logger = logging.getLogger(__name__)


def _build_provider(name: str, settings) -> LLMProvider:
    if name == "gemini":
        return GeminiProvider(api_key=settings.gemini_api_key)
    if name == "groq":
        return GroqProvider(api_key=settings.groq_api_key)
    if name == "huggingface":
        return HuggingFaceProvider(api_key=settings.huggingface_api_key)
    raise ValueError(f"Unknown LLM provider '{name}' in llm_provider_order")


def get_ordered_providers() -> List[LLMProvider]:
    settings = get_settings()
    order = [name.strip() for name in settings.llm_provider_order.split(",") if name.strip()]
    return [_build_provider(name, settings) for name in order]


async def generate_with_fallback(system_prompt: str, user_prompt: str) -> tuple[str, str]:
    """Returns (raw_text_response, provider_name_that_succeeded)."""
    providers = get_ordered_providers()
    attempted = []

    for provider in providers:
        attempted.append(provider.name)
        try:
            with log_duration(logger, "llm_call", provider=provider.name):
                text = await provider.generate(system_prompt, user_prompt)
            return text, provider.name
        except LLMProviderUnavailableError as exc:
            logger.warning(
                "llm_provider_failed_trying_next",
                extra={"event": "llm_provider_failed_trying_next", "provider": exc.provider},
            )
            continue

    raise AllLLMProvidersExhaustedError(attempted)
