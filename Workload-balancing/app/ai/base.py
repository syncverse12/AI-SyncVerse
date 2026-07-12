"""
ai/base.py
----------
                BaseLLMProvider
                        |
         +--------------+--------------+
         |              |              |
      Groq          Gemini        HuggingFace

Unified interface — no provider-specific logic exists outside this package.
Every concrete provider implements complete(prompt) -> raw text and the
factory handles ordering/fallback/retry.
"""

from __future__ import annotations
from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    name: str = "unset"

    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Returns raw text completion. Callers are responsible for JSON
        parsing/validation — this layer only knows how to talk to the API."""
        raise NotImplementedError

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError
