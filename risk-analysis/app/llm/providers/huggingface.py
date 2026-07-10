"""
Hugging Face Inference API provider — extra fallback / easy to swap the
underlying free model (e.g. Qwen2.5, Gemma) via `model_id` alone.
"""

import httpx
from app.llm.base import LLMProvider
from app.exceptions.llm import LLMProviderUnavailableError

HF_ENDPOINT_TEMPLATE = "https://api-inference.huggingface.co/models/{model_id}"


class HuggingFaceProvider(LLMProvider):
    name = "huggingface"

    def __init__(self, api_key: str, model_id: str = "Qwen/Qwen2.5-7B-Instruct", timeout_seconds: float = 20.0):
        self._api_key = api_key
        self._model_id = model_id
        self._timeout = timeout_seconds

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self._api_key:
            raise LLMProviderUnavailableError(self.name, "no API key configured")

        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {"inputs": full_prompt, "parameters": {"temperature": 0.2, "max_new_tokens": 800}}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    HF_ENDPOINT_TEMPLATE.format(model_id=self._model_id), json=payload, headers=headers
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
            return data[0]["generated_text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderUnavailableError(self.name, "unexpected response shape") from exc
