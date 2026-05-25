"""
app/services/drift_service.py
Bonus features:
  - Drift Detection: requirements that evolved but tasks haven't caught up
  - Predictive Risk Model: forecast future misalignment / delays
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.domain import (
    AlignmentScoreResult,
    HealthScoreResult,
    Priority,
    Project,
    RiskLevel,
    TaskStatus,
    PRIORITY_MULTIPLIER,
)

logger = get_logger(__name__)


@dataclass
class DriftSignal:
    requirement_id: str
    description: str
    alignment_score: float
    drift_type: str        # "semantic_drift" | "no_coverage" | "orphan_tasks"
    severity: RiskLevel


@dataclass
class DriftReport:
    project_id: str
    drift_detected: bool
    signals: List[DriftSignal]
    summary: str


@dataclass
class RiskForecast:
    project_id: str
    predicted_misalignment_risk: float      # 0–1
    predicted_delay_risk: float             # 0–1
    predicted_failure_risk: float           # 0–1
    overall_risk: RiskLevel
    risk_drivers: List[str]
    forecast_horizon_days: int = 14


def detect_drift(
    project: Project,
    alignment: AlignmentScoreResult,
) -> DriftReport:
    """
    Compare requirement alignment scores against task coverage.
    Flag when requirements have changed in meaning but tasks stay stale.
    """
    signals: List[DriftSignal] = []

    for req_detail in alignment.requirement_details:
        if req_detail.alert == "drift_detected":
            signals.append(DriftSignal(
                requirement_id=req_detail.requirement_id,
                description=req_detail.description,
                alignment_score=0.0,
                drift_type="no_coverage",
                severity=RiskLevel.CRITICAL,
            ))
        elif req_detail.alignment_score < 0.40:
            signals.append(DriftSignal(
                requirement_id=req_detail.requirement_id,
                description=req_detail.description,
                alignment_score=req_detail.alignment_score,
                drift_type="semantic_drift",
                severity=RiskLevel.HIGH,
            ))
        elif req_detail.alignment_score < 0.65:
            signals.append(DriftSignal(
                requirement_id=req_detail.requirement_id,
                description=req_detail.description,
                alignment_score=req_detail.alignment_score,
                drift_type="semantic_drift",
                severity=RiskLevel.MEDIUM,
            ))

    if alignment.orphan_task_ids:
        for tid in alignment.orphan_task_ids[:5]:
            signals.append(DriftSignal(
                requirement_id="N/A",
                description=f"Orphan task: {tid}",
                alignment_score=0.0,
                drift_type="orphan_tasks",
                severity=RiskLevel.MEDIUM,
            ))

    drift_detected = len(signals) > 0
    summary_parts = []
    if drift_detected:
        critical = [s for s in signals if s.severity == RiskLevel.CRITICAL]
        high = [s for s in signals if s.severity == RiskLevel.HIGH]
        summary_parts.append(
            f"Drift detected: {len(signals)} signal(s) "
            f"({len(critical)} critical, {len(high)} high severity)."
        )
    else:
        summary_parts.append("No significant drift detected.")

    return DriftReport(
        project_id=project.id,
        drift_detected=drift_detected,
        signals=signals,
        summary=" ".join(summary_parts),
    )


def predict_risk(
    project: Project,
    health: HealthScoreResult,
    alignment: AlignmentScoreResult,
    forecast_days: int = 14,
) -> RiskForecast:
    """
    Simple heuristic predictive model based on current trajectory.
    Scores are normalised 0–1 probabilities.
    """
    today = date.today()
    tasks = project.tasks
    drivers: List[str] = []

    # ── Misalignment risk ─────────────────────────────────────────────────────
    # Trend: if alignment is already low, extrapolate it getting worse
    current_alignment = alignment.alignment_score / 100
    misalignment_risk = max(0.0, 1.0 - current_alignment)
    if alignment.orphan_task_ids:
        misalignment_risk = min(1.0, misalignment_risk + 0.15)
        drivers.append("Orphan tasks diverting effort from requirements")
    if current_alignment < 0.5:
        drivers.append("Current alignment critically low")

    # ── Delay risk ────────────────────────────────────────────────────────────
    # Project upcoming deadlines in next N days
    upcoming_at_risk = [
        t for t in tasks
        if t.status != TaskStatus.COMPLETED
        and t.deadline
        and 0 <= (t.deadline - today).days <= forecast_days
    ]
    delay_risk = len(upcoming_at_risk) / max(len(tasks), 1)

    if health.delayed_tasks:
        delay_risk = min(1.0, delay_risk + len(health.delayed_tasks) * 0.05)
        drivers.append(f"{len(health.delayed_tasks)} tasks already delayed")

    critical_upcoming = [
        t for t in upcoming_at_risk if t.priority == Priority.CRITICAL
    ]
    if critical_upcoming:
        delay_risk = min(1.0, delay_risk + 0.2)
        drivers.append(f"{len(critical_upcoming)} critical tasks due within {forecast_days} days")

    # ── Failure risk ──────────────────────────────────────────────────────────
    # Weighted combination of both risks + health penalty
    health_norm = health.health_score / 100
    failure_risk = (
        0.40 * misalignment_risk
        + 0.35 * delay_risk
        + 0.25 * (1.0 - health_norm)
    )
    failure_risk = min(1.0, max(0.0, failure_risk))

    if failure_risk > 0.3:
        drivers.append(f"Combined health/alignment trajectory indicates elevated failure risk")

    # ── Overall risk level ────────────────────────────────────────────────────
    if failure_risk >= 0.70:
        overall = RiskLevel.CRITICAL
    elif failure_risk >= 0.45:
        overall = RiskLevel.HIGH
    elif failure_risk >= 0.25:
        overall = RiskLevel.MEDIUM
    else:
        overall = RiskLevel.LOW

    return RiskForecast(
        project_id=project.id,
        predicted_misalignment_risk=round(misalignment_risk, 3),
        predicted_delay_risk=round(delay_risk, 3),
        predicted_failure_risk=round(failure_risk, 3),
        overall_risk=overall,
        risk_drivers=drivers,
        forecast_horizon_days=forecast_days,
    )
