"""
Mode 1 — used when the backend exposes a single aggregated endpoint:

    GET /projects/{id}/risk-context

This is the fast path: one HTTP call instead of seven. If the endpoint
doesn't exist (404) or the backend is down, this collector raises so the
factory can fall back to Mode 2 — it never falls back internally, keeping
each mode single-purpose and independently testable.
"""

import logging
import httpx

from app.data_collector.base import DataCollector
from app.schemas.context_schema import ProjectContext, ProjectInfo
from app.exceptions.collector import (
    BackendUnavailableError,
    UnifiedEndpointNotSupportedError,
    ProjectNotFoundError,
)
from app.core.logging_config import log_duration

logger = logging.getLogger(__name__)


class UnifiedModeCollector(DataCollector):
    def __init__(self, http_client: httpx.AsyncClient):
        self._client = http_client

    async def collect(self, project_id: str) -> ProjectContext:
        endpoint = f"/projects/{project_id}/risk-context"

        with log_duration(logger, "unified_collector_call", endpoint=endpoint, project_id=project_id):
            try:
                response = await self._client.get(endpoint)
            except httpx.TimeoutException as exc:
                raise BackendUnavailableError(endpoint, "timeout") from exc
            except httpx.ConnectError as exc:
                raise BackendUnavailableError(endpoint, "connection refused") from exc

        if response.status_code == 404:
            raise UnifiedEndpointNotSupportedError(project_id)
        if response.status_code == 410:
            raise ProjectNotFoundError(project_id)
        if response.status_code >= 500:
            raise BackendUnavailableError(endpoint, f"HTTP {response.status_code}")

        response.raise_for_status()
        payload = response.json()
        return self._map_to_context(project_id, payload)

    @staticmethod
    def _map_to_context(project_id: str, payload: dict) -> ProjectContext:
        return ProjectContext(
            project=ProjectInfo(project_id=project_id, **payload.get("project", {})),
            tasks=payload.get("tasks", []),
            timeline=payload.get("timeline", []),
            milestones=payload.get("milestones", []),
            confirmed_risks=payload.get("risks", []),
            time_logs=payload.get("time_logs", []),
            team_members=payload.get("team_members", []),
            meetings=payload.get("meetings", []),
            collection_mode="unified",
            missing_sources=[],
            data_completeness=1.0,
        )
