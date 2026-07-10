"""
Groq provider (fallback). Uses llama-3.3-70b-versatile, OpenAI-compatible
chat completions endpoint.
"""

import httpx
from app.llm.base import LLMProvider
from app.exceptions.llm import LLMProviderUnavailableError

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile", timeout_seconds: float = 15.0):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self._api_key:
            raise LLMProviderUnavailableError(self.name, "no API key configured")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(GROQ_ENDPOINT, json=payload, headers=headers)
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
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMProviderUnavailableError(self.name, "unexpected response shape") from exc
