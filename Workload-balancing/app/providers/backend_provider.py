"""
providers/backend_provider.py
-------------------------------
Production data source. Talks ONLY to Backend REST APIs — never touches
SyncVerseDB directly, per the mandatory constraint in docs/DATABASE_ANALYSIS.md.

Expected REST contract (to be finalised with the backend team — this is the
integration seam, not a guess baked into business logic):

    GET {BACKEND_API_BASE_URL}/api/workload/employees?scope_type=&scope_id=
        -> [{id, first_name, last_name, seniority_level, department,
             skills_raw, availability_status, role}, ...]

    GET {BACKEND_API_BASE_URL}/api/workload/tasks?scope_type=&scope_id=
        -> [{id, title, description, status, priority, assigned_to_user_id,
             due_date, category_id, category_name, project_id, ...}, ...]
        (falls back to /api/workload/task-employees if empty AND
         BACKEND_ENABLE_TASK_EMPLOYEES_FALLBACK=true — see DB analysis §5)

    GET {BACKEND_API_BASE_URL}/api/workload/time-logs?scope_type=&scope_id=&since=
        -> [{id, task_id, user_id, start_time, end_time, duration_minutes}, ...]

Any single endpoint failing does not fail the whole snapshot — missing
pieces are logged as data_quality_warnings and the pipeline continues with
what it has (see ContextBuilder).
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Optional

import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type,
)

from app.config import get_settings
from app.providers.base import BaseDataProvider
from app.models.raw import RawTeamSnapshot, RawEmployee, RawTask, RawTimeLog
from app.core.exceptions import BackendUnavailableError
from app.core.logging import get_logger, timed

logger = get_logger(__name__)


class BackendDataProvider(BaseDataProvider):
    mode = "production"

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.BACKEND_API_BASE_URL:
            raise BackendUnavailableError(
                "BACKEND_API_BASE_URL is not configured — cannot run in production mode."
            )
        headers = {}
        if self._settings.BACKEND_API_KEY:
            headers["Authorization"] = f"Bearer {self._settings.BACKEND_API_KEY}"
        self._client = httpx.AsyncClient(
            base_url=self._settings.BACKEND_API_BASE_URL,
            timeout=self._settings.BACKEND_API_TIMEOUT_SECONDS,
            headers=headers,
        )

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/health")
            return resp.status_code < 500
        except httpx.HTTPError:
            return False

    def _retrying(self):
        s = self._settings
        return retry(
            reraise=True,
            stop=stop_after_attempt(s.BACKEND_API_RETRY_ATTEMPTS),
            wait=wait_exponential(
                min=s.BACKEND_API_RETRY_MIN_WAIT, max=s.BACKEND_API_RETRY_MAX_WAIT
            ),
            retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        )

    async def _get(self, path: str, params: dict) -> list:
        @self._retrying()
        async def _call():
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()

        try:
            with timed(logger, "backend_api_call", path=path):
                return await _call()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning(f"Backend endpoint failed after retries: {path}", extra={"error": str(exc)})
            raise BackendUnavailableError(f"{path} unavailable: {exc}") from exc

    async def get_team_snapshot(self, scope_type: str, scope_id: str) -> RawTeamSnapshot:
        params = {"scope_type": scope_type, "scope_id": scope_id}
        warnings: List[str] = []

        employees_raw = await self._safe_fetch("/api/workload/employees", params, warnings, "employees")
        tasks_raw = await self._safe_fetch("/api/workload/tasks", params, warnings, "tasks")

        if not tasks_raw and self._settings.BACKEND_ENABLE_TASK_EMPLOYEES_FALLBACK:
            logger.warning(
                "Primary Tasks endpoint returned nothing — falling back to TaskEmployees",
                extra={"scope_id": scope_id},
            )
            tasks_raw = await self._safe_fetch(
                "/api/workload/task-employees", params, warnings, "tasks (fallback: task_employees)"
            )
            for t in tasks_raw:
                t.setdefault("title", t.get("task_title", "Untitled"))

        since = (datetime.utcnow() - timedelta(days=self._settings.CAPACITY_LOOKBACK_DAYS)).isoformat()
        time_logs_raw = await self._safe_fetch(
            "/api/workload/time-logs", {**params, "since": since}, warnings, "time_logs"
        )

        employees = [RawEmployee.model_validate(e) for e in employees_raw]
        tasks = [RawTask.model_validate(t) for t in tasks_raw]
        time_logs = [RawTimeLog.model_validate(t) for t in time_logs_raw]

        return RawTeamSnapshot(
            scope_type=scope_type,
            scope_id=scope_id,
            employees=employees,
            tasks=tasks,
            time_logs=time_logs,
            data_quality_warnings=warnings,
        )

    async def _safe_fetch(self, path: str, params: dict, warnings: List[str], label: str) -> list:
        try:
            return await self._get(path, params)
        except BackendUnavailableError as exc:
            warnings.append(f"{label} unavailable: {exc}")
            return []

    async def list_available_scopes(self) -> List[dict]:
        try:
            return await self._get("/api/workload/scopes", {})
        except BackendUnavailableError:
            return []

    async def aclose(self) -> None:
        await self._client.aclose()
