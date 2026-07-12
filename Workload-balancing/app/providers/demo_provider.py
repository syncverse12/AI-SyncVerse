"""
providers/demo_provider.py
---------------------------
Loads realistic fixtures from local JSON. Never calls the backend, never
requires a DB. Runs the exact same downstream pipeline as Production —
only the data source differs.
"""

from __future__ import annotations
import json
import os
from typing import Dict, List

from app.providers.base import BaseDataProvider
from app.models.raw import RawTeamSnapshot
from app.core.exceptions import ContextBuildError
from app.core.logging import get_logger

logger = get_logger(__name__)

_DEMO_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "demo")

SCENARIO_NAMES = [
    "normal_project",
    "overloaded_team",
    "underutilized_team",
    "delayed_project",
    "high_priority_project",
    "critical_project",
]


class DemoDataProvider(BaseDataProvider):
    mode = "demo"

    def __init__(self, demo_dir: str = _DEMO_DIR) -> None:
        self._demo_dir = demo_dir
        self._cache: Dict[str, RawTeamSnapshot] = {}

    async def get_team_snapshot(self, scope_type: str, scope_id: str) -> RawTeamSnapshot:
        # In demo mode, scope_id IS the scenario name (e.g. "overloaded_team").
        scenario = scope_id if scope_id in SCENARIO_NAMES else "normal_project"
        if scenario not in self._cache:
            path = os.path.join(self._demo_dir, f"{scenario}.json")
            if not os.path.exists(path):
                raise ContextBuildError(f"Unknown demo scenario: {scenario}")
            with open(path, "r") as f:
                data = json.load(f)
            self._cache[scenario] = RawTeamSnapshot.model_validate(data)
            logger.info("Loaded demo scenario", extra={"scenario": scenario})
        return self._cache[scenario]

    async def list_available_scopes(self) -> List[dict]:
        return [
            {"scope_type": "project", "scope_id": name, "scope_name": name.replace("_", " ").title()}
            for name in SCENARIO_NAMES
        ]
