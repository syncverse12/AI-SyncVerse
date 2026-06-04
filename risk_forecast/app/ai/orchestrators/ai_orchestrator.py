"""
AI Orchestrator — decoupled from business logic.
Handles LLM provider switching, retry, structured output parsing.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AIOrchestrator:
    """
    Provider-agnostic AI client.
    Swap OpenAI <-> Gemini by changing AI_PROVIDER env var.
    """

    def __init__(self) -> None:
        self._openai: AsyncOpenAI | None = None

    @property
    def openai(self) -> AsyncOpenAI:
        if self._openai is None:
            self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai

    # ── Core completion ──────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, Exception)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """
        Call the configured AI provider and return raw text.
        Low temperature (0.2) ensures consistent, calibrated risk scores.
        """
        provider = settings.ai_provider

        if provider == "openai":
            return await self._openai_complete(
                system_prompt, user_prompt, temperature, max_tokens
            )
        elif provider == "gemini":
            return await self._gemini_complete(
                system_prompt, user_prompt, temperature, max_tokens
            )
        else:
            raise ValueError(f"Unknown AI provider: {provider}")

    async def _openai_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        logger.debug("OpenAI completion request", model=settings.openai_model)
        response = await self.openai.chat.completions.create(
            model=settings.openai_model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},  # guaranteed JSON output
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""

    async def _gemini_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Gemini via REST API — swap to google-generativeai SDK if preferred."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.gemini_model}:generateContent",
                params={"key": settings.gemini_api_key},
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": f"{system_prompt}\n\n{user_prompt}"}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens,
                        "responseMimeType": "application/json",
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    # ── Structured output ────────────────────────────────────────────────────

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        Complete and parse JSON. Raises ValueError on parse failure.
        """
        raw = await self.complete(
            system_prompt, user_prompt, temperature=temperature, max_tokens=max_tokens
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("AI returned invalid JSON", raw=raw[:500], error=str(exc))
            raise ValueError(f"AI response was not valid JSON: {exc}") from exc

    # ── Embeddings ───────────────────────────────────────────────────────────

    async def embed(self, text: str) -> list[float]:
        """Generate embedding vector for RAG storage/retrieval."""
        response = await self.openai.embeddings.create(
            model=settings.openai_embedding_model,
            input=text,
        )
        return response.data[0].embedding


# Singleton — injected via FastAPI dependency
_orchestrator: AIOrchestrator | None = None


def get_orchestrator() -> AIOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AIOrchestrator()
    return _orchestrator
