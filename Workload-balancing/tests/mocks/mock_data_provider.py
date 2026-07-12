"""
tests/mocks/mock_data_provider.py
------------------------------------
In-memory BaseDataProvider for tests — avoids touching demo JSON files or
the real backend.
"""
from __future__ import annotations
from typing import List
from app.providers.base import BaseDataProvider
from app.models.raw import RawTeamSnapshot


class MockDataProvider(BaseDataProvider):
    mode = "mock"

    def __init__(self, snapshot: RawTeamSnapshot):
        self._snapshot = snapshot

    async def get_team_snapshot(self, scope_type: str, scope_id: str) -> RawTeamSnapshot:
        return self._snapshot

    async def list_available_scopes(self) -> List[dict]:
        return [{"scope_type": self._snapshot.scope_type, "scope_id": self._snapshot.scope_id,
                  "scope_name": self._snapshot.scope_name}]
