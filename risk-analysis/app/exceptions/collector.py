"""
Exceptions raised by the Data Collector layer.

Keeping these separate from generic Python exceptions lets the Orchestrator
decide precisely how to react (retry, fall back to Mode 2, degrade a metric,
or fail the whole request) instead of catching bare `Exception`.
"""

from typing import List, Optional


class DataCollectorError(Exception):
    """Base class for every error raised while collecting project data."""


class BackendUnavailableError(DataCollectorError):
    """
    Raised when the backend cannot be reached at all (timeout, connection
    refused, 5xx). This is the trigger to fall back from Mode 1 to Mode 2,
    or, if already in Mode 2, to mark the whole collection as failed.
    """

    def __init__(self, endpoint: str, reason: str):
        self.endpoint = endpoint
        self.reason = reason
        super().__init__(f"Backend unavailable at {endpoint}: {reason}")


class UnifiedEndpointNotSupportedError(DataCollectorError):
    """
    Raised specifically when GET /projects/{id}/risk-context returns 404,
    meaning this backend simply doesn't implement the aggregated endpoint.
    This is an expected, non-fatal condition that should silently trigger
    Mode 2 rather than being logged as an error.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        super().__init__(
            f"Unified risk-context endpoint not available for project {project_id}"
        )


class PartialDataError(DataCollectorError):
    """
    Raised (as a *carried* condition, not necessarily re-raised) when Mode 2
    successfully collects some sources but not others. The Orchestrator uses
    `missing_sources` to decide which downstream metrics must degrade to
    AI Estimated instead of Deterministic.
    """

    def __init__(self, missing_sources: List[str], partial_context: Optional[dict] = None):
        self.missing_sources = missing_sources
        self.partial_context = partial_context or {}
        super().__init__(f"Missing data sources: {', '.join(missing_sources)}")


class ProjectNotFoundError(DataCollectorError):
    """Raised when the project_id itself does not exist in the backend."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        super().__init__(f"Project {project_id} not found")
