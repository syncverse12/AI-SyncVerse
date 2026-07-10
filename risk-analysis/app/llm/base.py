"""LLM provider interface every concrete provider must implement."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return the raw text response. Callers are responsible for parsing JSON."""
        raise NotImplementedError
