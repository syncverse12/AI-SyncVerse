from __future__ import annotations
import httpx

from app.ai.base import BaseLLMProvider
from app.config import get_settings
from app.core.exceptions import LLMProviderError


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(self) -> None:
        self._settings = get_settings()

    def is_configured(self) -> bool:
        return bool(self._settings.GEMINI_API_KEY)

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.is_configured():
            raise LLMProviderError("Gemini API key not configured")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._settings.GEMINI_MODEL}:generateContent?key={self._settings.GEMINI_API_KEY}"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        }
        try:
            async with httpx.AsyncClient(timeout=self._settings.GEMINI_TIMEOUT_SECONDS) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMProviderError(f"Gemini call failed: {exc}") from exc
