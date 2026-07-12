"""
risk_analyzer.py
----------------
Ingests WorkloadMetrics and produces a structured RiskReport that describes:

  * which employees are overloaded / underutilized / bottlenecks
  * the overall team balance status
  * a team health score (0-100)

This module contains NO recommendation logic — that lives in
redistribution_engine.py.  The separation keeps concerns clean and each
module independently testable.
"""

from __future__ import annotations
import logging
import statistics
from dataclasses import dataclass, field
from typing import List

from app.models.schemas import (
    BalanceStatus,
    RiskLevel,
    WorkloadMetrics,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Team health degrades proportionally with the number of high-risk employees
HEALTH_PENALTY_HIGH_RISK = 15.0    # points deducted per high-risk employee
HEALTH_PENALTY_MEDIUM_RISK = 5.0
HEALTH_PENALTY_BOTTLENECK = 10.0
HEALTH_BONUS_LOW_RISK = 2.0        # small bonus for each healthy employee

CRITICAL_IMBALANCE_THRESHOLD = 3   # ≥N overloaded employees → critical


# ---------------------------------------------------------------------------
# Internal data structure (not exposed outside the balancing package)
# ---------------------------------------------------------------------------

@dataclass
class RiskReport:
    status: BalanceStatus
    team_health_score: float
    overloaded: List[WorkloadMetrics] = field(default_factory=list)
    underutilized: List[WorkloadMetrics] = field(default_factory=list)
    bottlenecks: List[WorkloadMetrics] = field(default_factory=list)
    summary: str = ""
    score_variance: float = 0.0   # spread metric — high variance → imbalance


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------

class RiskAnalyzer:
    """
    Pure analysis layer.  Stateless — instantiate once and call analyse()
    as many times as needed.
    """

    def analyse(self, metrics: List[WorkloadMetrics]) -> RiskReport:
        if not metrics:
            return RiskReport(
                status=BalanceStatus.BALANCED,
                team_health_score=100.0,
                summary="No employee data provided.",
            )

        overloaded = [m for m in metrics if m.is_overloaded]
        underutilized = [m for m in metrics if m.is_underutilized]
        bottlenecks = [m for m in metrics if m.is_bottleneck]

        health = self._compute_health(metrics, overloaded, underutilized, bottlenecks)
        status = self._determine_status(overloaded, bottlenecks)
        variance = self._score_variance(metrics)
        summary = self._build_summary(
            metrics, overloaded, underutilized, bottlenecks, health, status
        )

        report = RiskReport(
            status=status,
            team_health_score=round(health, 1),
            overloaded=overloaded,
            underutilized=underutilized,
            bottlenecks=bottlenecks,
            summary=summary,
            score_variance=round(variance, 2),
        )

        logger.info(
            "RiskAnalyzer: status=%s health=%.1f overloaded=%d underutilized=%d bottlenecks=%d",
            status, health, len(overloaded), len(underutilized), len(bottlenecks),
        )
        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_health(
        metrics: List[WorkloadMetrics],
        overloaded: List[WorkloadMetrics],
        underutilized: List[WorkloadMetrics],
        bottlenecks: List[WorkloadMetrics],
    ) -> float:
        score = 100.0

        high_risk = [m for m in metrics if m.risk_level == RiskLevel.HIGH]
        medium_risk = [m for m in metrics if m.risk_level == RiskLevel.MEDIUM]
        low_risk = [m for m in metrics if m.risk_level == RiskLevel.LOW]

        score -= len(high_risk) * HEALTH_PENALTY_HIGH_RISK
        score -= len(medium_risk) * HEALTH_PENALTY_MEDIUM_RISK
        score -= len(bottlenecks) * HEALTH_PENALTY_BOTTLENECK
        score += len(low_risk) * HEALTH_BONUS_LOW_RISK

        # Extra penalty when workload spread is extreme
        variance = RiskAnalyzer._score_variance(metrics)
        if variance > 500:
            score -= 10
        elif variance > 300:
            score -= 5

        return max(0.0, min(100.0, score))

    @staticmethod
    def _determine_status(
        overloaded: List[WorkloadMetrics],
        bottlenecks: List[WorkloadMetrics],
    ) -> BalanceStatus:
        if not overloaded and not bottlenecks:
            return BalanceStatus.BALANCED
        if len(overloaded) >= CRITICAL_IMBALANCE_THRESHOLD or len(bottlenecks) >= 2:
            return BalanceStatus.CRITICAL_IMBALANCE
        return BalanceStatus.IMBALANCE_DETECTED

    @staticmethod
    def _score_variance(metrics: List[WorkloadMetrics]) -> float:
        if len(metrics) < 2:
            return 0.0
        scores = [m.risk_score for m in metrics]
        return statistics.variance(scores)

    @staticmethod
    def _build_summary(
        metrics: List[WorkloadMetrics],
        overloaded: List[WorkloadMetrics],
        underutilized: List[WorkloadMetrics],
        bottlenecks: List[WorkloadMetrics],
        health: float,
        status: BalanceStatus,
    ) -> str:
        parts: List[str] = [
            f"Team of {len(metrics)} · Health {health:.0f}/100 · Status: {status.value}."
        ]

        if overloaded:
            names = ", ".join(m.employee_name for m in overloaded)
            parts.append(f"⚠ Overloaded: {names}.")
        if underutilized:
            names = ", ".join(m.employee_name for m in underutilized)
            parts.append(f"📉 Underutilized: {names}.")
        if bottlenecks:
            names = ", ".join(m.employee_name for m in bottlenecks)
            parts.append(f"🔴 Bottlenecks: {names}.")
        if not overloaded and not underutilized and not bottlenecks:
            parts.append("✅ Workload is evenly distributed.")

        return " ".join(parts)
