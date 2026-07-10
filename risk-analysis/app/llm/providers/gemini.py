"""
Gemini provider (primary, free tier). Talks to the Generative Language API
directly over HTTP so we don't need the full google-generativeai SDK as a
dependency — keeps the image small for Hugging Face Spaces.
"""

import httpx
from app.llm.base import LLMProvider
from app.exceptions.llm import LLMProviderUnavailableError

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, timeout_seconds: float = 15.0):
        self._api_key = api_key
        self._timeout = timeout_seconds

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self._api_key:
            raise LLMProviderUnavailableError(self.name, "no API key configured")

        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{GEMINI_ENDPOINT}?key={self._api_key}", json=payload
                )
        except httpx.TimeoutException as exc:
            raise LLMProviderUnavailableError(self.name, "timeout") from exc
        except httpx.ConnectError as exc:
            raise LLMProviderUnavailableError(self.name, "connection error") from exc

        if response.status_code == 429:
            raise LLMProviderUnavailableError(self.name, "rate limited (429)")
        if response.status_code >= 400:
            raise LLMProviderUnavailableError(self.name, f"HTTP {response.status_code}")

        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise LLMProviderUnavailableError(self.name, "unexpected response shape") from exc
