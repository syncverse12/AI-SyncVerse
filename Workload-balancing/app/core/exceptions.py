"""
core/exceptions.py
-------------------
Custom exception hierarchy. Every layer raises one of these instead of
leaking raw HTTPX/SDK/parsing errors, so the Report Builder and route
handlers can degrade gracefully instead of crashing the whole request.
"""

from __future__ import annotations


class WorkloadServiceError(Exception):
    """Base class for all service-specific errors."""


class BackendUnavailableError(WorkloadServiceError):
    """Backend REST API could not be reached or returned a server error
    after all retries were exhausted."""


class ContextBuildError(WorkloadServiceError):
    """Raw provider data could not be assembled into a valid WorkloadContext."""


class MetricsCalculationError(WorkloadServiceError):
    """Deterministic metrics engine failed on otherwise-valid context data."""


class LLMProviderError(WorkloadServiceError):
    """A single LLM provider call failed (network, auth, malformed response)."""


class ProviderNotConfiguredError(WorkloadServiceError):
    """No LLM provider has valid credentials configured — enrichment must
    fall back to deterministic-only defaults."""


class ReportGenerationError(WorkloadServiceError):
    """The Report Builder could not assemble a final response."""
