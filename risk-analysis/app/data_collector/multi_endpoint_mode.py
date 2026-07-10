"""
Mode 2 — used when the backend has no aggregated /risk-context endpoint.

Fetches each source independently (projects, tasks, timeline, milestones,
risks, time_logs, meetings). Each source is retried on its own with
tenacity; if a source still fails after retries, it's recorded in
`missing_sources` and the collector degrades gracefully instead of failing
the whole request — the Risk Engine will simply mark any metric that
depends on that source as lower-confidence / AI Estimated.
"""

import asyncio
import logging
import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)

from app.data_collector.base import DataCollector
from app.schemas.context_schema import ProjectContext, ProjectInfo
from app.exceptions.collector import BackendUnavailableError, ProjectNotFoundError
from app.core.logging_config import log_duration

logger = logging.getLogger(__name__)

# One entry per independent source. Endpoint + the ProjectContext field it fills.
SOURCES = [
    ("tasks", "/projects/{id}/tasks"),
    ("timeline", "/projects/{id}/timeline"),
    ("milestones", "/projects/{id}/milestones"),
    ("risks", "/projects/{id}/risks"),
    ("time_logs", "/projects/{id}/timelogs"),
    ("team_members", "/projects/{id}/team-members"),
    ("meetings", "/projects/{id}/team-meetings"),
]


class MultiEndpointModeCollector(DataCollector):
    def __init__(self, http_client: httpx.AsyncClient):
        self._client = http_client

    async def collect(self, project_id: str) -> ProjectContext:
        # Project info is mandatory — if this fails, the whole request fails.
        project_info = await self._fetch_project(project_id)

        results = await asyncio.gather(
            *[self._fetch_source(project_id, name, path) for name, path in SOURCES],
            return_exceptions=True,
        )

        context_data: dict = {}
        missing_sources: list = []
        for (name, _), result in zip(SOURCES, results):
            if isinstance(result, Exception):
                logger.warning(
                    "source_unavailable_after_retries",
                    extra={"event": "source_unavailable_after_retries", "endpoint": name, "project_id": project_id},
                )
                context_data[name] = []
                missing_sources.append(name)
            else:
                context_data[name] = result

        completeness = 1.0 - (len(missing_sources) / len(SOURCES))

        return ProjectContext(
            project=project_info,
            tasks=context_data["tasks"],
            timeline=context_data["timeline"],
            milestones=context_data["milestones"],
            confirmed_risks=context_data["risks"],
            time_logs=context_data["time_logs"],
            team_members=context_data["team_members"],
            meetings=context_data["meetings"],
            collection_mode="multi_endpoint",
            missing_sources=missing_sources,
            data_completeness=round(completeness, 2),
        )

    async def _fetch_project(self, project_id: str) -> ProjectInfo:
        endpoint = f"/projects/{project_id}"
        try:
            response = await self._retryable_get(endpoint)
        except Exception as exc:
            raise BackendUnavailableError(endpoint, str(exc)) from exc

        if response.status_code == 404:
            raise ProjectNotFoundError(project_id)
        response.raise_for_status()
        return ProjectInfo(project_id=project_id, **response.json())

    async def _fetch_source(self, project_id: str, name: str, path_template: str):
        endpoint = path_template.format(id=project_id)
        with log_duration(logger, "multi_endpoint_source_call", endpoint=name, project_id=project_id):
            response = await self._retryable_get(endpoint)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _retryable_get(self, endpoint: str) -> httpx.Response:
        return await self._client.get(endpoint)
