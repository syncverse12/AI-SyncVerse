"""Exceptions raised by the LLM layer."""


class LLMError(Exception):
    """Base class for every LLM-related error."""


class LLMProviderUnavailableError(LLMError):
    """A single provider (e.g. Gemini) failed — may still fall back to the next one."""

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"LLM provider '{provider}' unavailable: {reason}")


class AllLLMProvidersExhaustedError(LLMError):
    """Every configured provider failed. Callers must degrade AI Estimated
    metrics to a documented default rather than crash the whole report."""

    def __init__(self, attempted_providers: list):
        self.attempted_providers = attempted_providers
        super().__init__(f"All LLM providers failed: {', '.join(attempted_providers)}")


class LLMResponseParsingError(LLMError):
    """The provider replied, but the response wasn't valid JSON / didn't match schema."""

    def __init__(self, provider: str, raw_snippet: str):
        self.provider = provider
        self.raw_snippet = raw_snippet[:200]
        super().__init__(f"Could not parse response from '{provider}': {self.raw_snippet}")
