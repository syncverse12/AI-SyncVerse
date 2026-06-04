"""
Risk Repository — all database access for the risk engine.
Follows the repository pattern: no SQL in service layer.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.orm import AlertORM, MetricsSnapshot, Project, RiskReportORM
from app.models.schemas import AlertPayload, AlertStatus, LiveProjectMetrics, RiskReport

logger = get_logger(__name__)


class RiskRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Reports ──────────────────────────────────────────────────────────────

    async def save_report(self, report: RiskReport) -> None:
        orm = RiskReportORM(
            id=report.report_id,
            project_id=report.project_id,
            report_type=report.report_type,
            overall_risk_score=report.scores.overall,
            severity=report.scores.severity.value,
            delay_probability=report.delay_probability,
            budget_overrun_probability=report.budget_overrun_probability,
            delivery_confidence=report.delivery_confidence,
            burnout_probability=report.burnout_probability,
            confidence=report.scores.confidence,
            report_json=report.model_dump(),
            generated_at=report.generated_at,
        )
        self._db.add(orm)
        await self._db.flush()
        logger.debug("Report persisted", report_id=str(report.report_id))

    async def get_latest_report(self, project_id: UUID) -> RiskReport | None:
        result = await self._db.execute(
            select(RiskReportORM)
            .where(RiskReportORM.project_id == project_id)
            .order_by(desc(RiskReportORM.generated_at))
            .limit(1)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return RiskReport(**orm.report_json)

    # ── Metrics snapshots ─────────────────────────────────────────────────────

    async def save_metrics_snapshot(
        self, metrics: LiveProjectMetrics, overall_score: float
    ) -> None:
        snap = MetricsSnapshot(
            project_id=metrics.project_id,
            snapshot_at=metrics.snapshot_at,
            overall_risk_score=overall_score,
            metrics_json=metrics.model_dump(),
        )
        self._db.add(snap)
        await self._db.flush()

    async def get_metrics_history(
        self, project_id: UUID, limit: int = 30
    ) -> list[dict]:
        result = await self._db.execute(
            select(MetricsSnapshot)
            .where(MetricsSnapshot.project_id == project_id)
            .order_by(desc(MetricsSnapshot.snapshot_at))
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "snapshot_at": r.snapshot_at.isoformat(),
                "overall_risk_score": r.overall_risk_score,
            }
            for r in reversed(rows)
        ]

    # ── Active projects ───────────────────────────────────────────────────────

    async def get_active_project_ids(self) -> list[UUID]:
        result = await self._db.execute(
            select(Project.id).where(Project.status == "active")
        )
        return list(result.scalars().all())


class AlertRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, alert: AlertPayload) -> None:
        orm = AlertORM(
            id=alert.alert_id,
            project_id=alert.project_id,
            severity=alert.severity.value,
            risk_category=alert.risk_category.value,
            status=alert.status.value,
            title=alert.title,
            message=alert.message,
            root_cause=alert.root_cause,
            ai_insight=alert.ai_insight,
            recommended_action=alert.recommended_action,
            previous_risk_score=alert.previous_risk_score,
            current_risk_score=alert.current_risk_score,
            delta=alert.delta,
            escalation_level=alert.escalation_level,
            notify_roles=alert.notify_roles,
            fired_at=alert.fired_at,
        )
        self._db.add(orm)
        await self._db.flush()
        logger.info("Alert persisted", alert_id=str(alert.alert_id))

    async def list_alerts(
        self,
        project_id: UUID | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        query = select(AlertORM).order_by(desc(AlertORM.fired_at)).limit(limit)
        if project_id:
            query = query.where(AlertORM.project_id == project_id)
        if severity:
            query = query.where(AlertORM.severity == severity.upper())
        result = await self._db.execute(query)
        rows = result.scalars().all()
        return [
            {
                "alert_id": str(r.id),
                "project_id": str(r.project_id),
                "severity": r.severity,
                "risk_category": r.risk_category,
                "status": r.status,
                "title": r.title,
                "message": r.message,
                "ai_insight": r.ai_insight,
                "recommended_action": r.recommended_action,
                "previous_risk_score": r.previous_risk_score,
                "current_risk_score": r.current_risk_score,
                "delta": r.delta,
                "escalation_level": r.escalation_level,
                "fired_at": r.fired_at.isoformat(),
            }
            for r in rows
        ]

    async def acknowledge(
        self, alert_id: UUID, acknowledged_by: str, note: str | None
    ) -> bool:
        result = await self._db.execute(
            select(AlertORM).where(AlertORM.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if alert is None:
            return False
        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        await self._db.flush()
        return True
