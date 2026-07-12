from __future__ import annotations
import httpx

from app.ai.base import BaseLLMProvider
from app.config import get_settings
from app.core.exceptions import LLMProviderError


class GroqProvider(BaseLLMProvider):
    name = "groq"
    _URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self) -> None:
        self._settings = get_settings()

    def is_configured(self) -> bool:
        return bool(self._settings.GROQ_API_KEY)

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.is_configured():
            raise LLMProviderError("Groq API key not configured")
        headers = {"Authorization": f"Bearer {self._settings.GROQ_API_KEY}"}
        payload = {
            "model": self._settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=self._settings.GROQ_TIMEOUT_SECONDS) as client:
                resp = await client.post(self._URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMProviderError(f"Groq call failed: {exc}") from exc
