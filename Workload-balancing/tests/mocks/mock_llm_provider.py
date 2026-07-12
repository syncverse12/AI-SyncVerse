"""
tests/mocks/mock_llm_provider.py
----------------------------------
Fake BaseLLMProvider used by unit/integration tests so no network access
(and no real API keys) is required to test the AI Enrichment layer.
"""
from __future__ import annotations
import json
from app.ai.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def __init__(self, response: dict | None = None, should_fail: bool = False):
        self._response = response or {"employees": {}}
        self._should_fail = should_fail

    def is_configured(self) -> bool:
        return True

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        if self._should_fail:
            from app.core.exceptions import LLMProviderError
            raise LLMProviderError("mock failure")
        return json.dumps(self._response)
