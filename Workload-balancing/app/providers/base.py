"""
providers/base.py
------------------
                BaseDataProvider
                        |
         +--------------+--------------+
         |                             |
   DemoDataProvider           BackendDataProvider

Business logic (Context Builder onward) only ever talks to this interface.
It never knows which concrete provider is behind it.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List

from app.models.raw import RawTeamSnapshot


class BaseDataProvider(ABC):
    mode: str = "unset"

    @abstractmethod
    async def get_team_snapshot(self, scope_type: str, scope_id: str) -> RawTeamSnapshot:
        """Fetch everything needed for one analysis run: employees, their
        active/relevant tasks, and recent time logs, scoped to a project,
        team, or workspace."""
        raise NotImplementedError

    @abstractmethod
    async def list_available_scopes(self) -> List[dict]:
        """Returns [{scope_type, scope_id, scope_name}, ...] — used by the
        /scopes endpoint and by Demo mode's scenario picker."""
        raise NotImplementedError

    async def health_check(self) -> bool:
        """Overridden by providers that have something worth checking
        (e.g. BackendDataProvider pinging the REST API)."""
        return True
