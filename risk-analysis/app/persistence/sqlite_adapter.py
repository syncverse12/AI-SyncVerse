"""
SQLite implementation of the Internal Persistence Layer. Default backend —
stateless from the caller's perspective (the service holds no in-memory
state between requests), but this file itself persists reports/snapshots
to a local .db file, which is what makes historical trend metrics possible
on Hugging Face Spaces' ephemeral-but-locally-writable filesystem.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from app.persistence.base import PersistenceAdapter
from app.schemas.report_schema import RiskReport
from app.core.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    report_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_project_id ON reports(project_id);

CREATE TABLE IF NOT EXISTS snapshots (
    project_id TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    snapshot_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_project_id ON snapshots(project_id);
"""


class SQLitePersistenceAdapter(PersistenceAdapter):
    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or get_settings().sqlite_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    async def save_report(self, report: RiskReport) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO reports (project_id, generated_at, report_json) VALUES (?, ?, ?)",
                (
                    report.metadata.project_id,
                    report.metadata.generated_at.isoformat(),
                    report.model_dump_json(),
                ),
            )

    async def get_report_history(self, project_id: str, limit: int = 20) -> List[RiskReport]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT report_json FROM reports WHERE project_id = ? "
                "ORDER BY generated_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [RiskReport.model_validate(json.loads(row[0])) for row in rows]

    async def save_snapshot(self, project_id: str, snapshot: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO snapshots (project_id, captured_at, snapshot_json) VALUES (?, ?, ?)",
                (project_id, datetime.now(timezone.utc).isoformat(), json.dumps(snapshot)),
            )

    async def get_latest_snapshot(self, project_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT snapshot_json FROM snapshots WHERE project_id = ? "
                "ORDER BY captured_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None
