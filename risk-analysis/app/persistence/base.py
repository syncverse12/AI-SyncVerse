"""
Internal Persistence Layer interface. Used for two things:
  1. Storing generated reports (for GET /projects/{id}/history).
  2. Storing lightweight historical snapshots (progress %, task count over
     time) so Scope Risk / Schedule Stability trends can be derived later
     without needing new backend database columns.

Swappable to Postgres/Redis later without touching any calling code.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.report_schema import RiskReport


class PersistenceAdapter(ABC):
    @abstractmethod
    async def save_report(self, report: RiskReport) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_report_history(self, project_id: str, limit: int = 20) -> List[RiskReport]:
        raise NotImplementedError

    @abstractmethod
    async def save_snapshot(self, project_id: str, snapshot: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_latest_snapshot(self, project_id: str) -> Optional[dict]:
        raise NotImplementedError
