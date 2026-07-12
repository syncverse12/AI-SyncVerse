"""
workload_monitor.py
-------------------
Calculates workload scores and risk classifications for every employee.

Formula:
    WorkloadScore = (ActiveTasks × ComplexityWeight)
                  + (DelayedTasks × 2)
                  - AvailabilityScore

ComplexityWeight is derived from the employee's task complexity distribution.
"""

from __future__ import annotations
import logging
from typing import List, Dict, Tuple

from app.models.schemas import (
    Employee,
    WorkloadMetrics,
    RiskLevel,
    TaskComplexityDistribution,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable constants — externalise to config/env in production
# ---------------------------------------------------------------------------

COMPLEXITY_WEIGHTS: Dict[str, float] = {
    "low": 0.5,
    "medium": 1.0,
    "high": 1.8,
    "critical": 3.0,
}

RISK_THRESHOLDS = {
    RiskLevel.LOW: (float("-inf"), 30),
    RiskLevel.MEDIUM: (30, 60),
    RiskLevel.HIGH: (60, float("inf")),
}

OVERLOAD_SCORE_THRESHOLD = 60.0
UNDERUTILIZED_SCORE_THRESHOLD = 10.0
BOTTLENECK_DELAYED_RATIO = 0.4   # delayed / active > 40 % → bottleneck


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class WorkloadMonitor:
    """
    Stateless calculator. Feed it a list of Employee objects and it returns
    a list of WorkloadMetrics — one per employee.
    """

    def analyse(self, employees: List[Employee]) -> List[WorkloadMetrics]:
        """
        Main entry-point. Returns metrics for every employee.
        """
        if not employees:
            return []

        raw_scores = [self._compute_raw_score(e) for e in employees]
        normalised = self._normalise_scores(raw_scores)

        metrics: List[WorkloadMetrics] = []
        for employee, (raw, cw), risk_score in zip(employees, raw_scores, normalised):
            risk_level, reason = self._classify_risk(employee, raw, risk_score)
            overloaded = risk_score >= OVERLOAD_SCORE_THRESHOLD
            underutilized = self._is_underutilized(employee, risk_score)
            bottleneck = self._is_bottleneck(employee)

            metrics.append(
                WorkloadMetrics(
                    employee_id=employee.id,
                    employee_name=employee.name,
                    workload_score=round(raw, 2),
                    complexity_weight=round(cw, 2),
                    risk_level=risk_level,
                    risk_score=round(risk_score, 2),
                    reason=reason,
                    is_overloaded=overloaded,
                    is_underutilized=underutilized,
                    is_bottleneck=bottleneck,
                )
            )

        logger.info(
            "WorkloadMonitor.analyse: processed %d employees, "
            "overloaded=%d, underutilized=%d",
            len(employees),
            sum(1 for m in metrics if m.is_overloaded),
            sum(1 for m in metrics if m.is_underutilized),
        )
        return metrics

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_raw_score(self, emp: Employee) -> Tuple[float, float]:
        """
        Returns (raw_workload_score, effective_complexity_weight).
        """
        cw = _effective_complexity_weight(emp.task_complexity_distribution)
        score = (
            (emp.active_tasks * cw)
            + (emp.delayed_tasks * 2)
            - (emp.availability_score / 10)  # scale 0-100 → 0-10
        )
        return score, cw

    @staticmethod
    def _normalise_scores(raw_and_weights: List[Tuple[float, float]]) -> List[float]:
        """
        Min-max normalise raw scores to [0, 100].
        If all scores are identical, return 50 for everyone.
        """
        raws = [r for r, _ in raw_and_weights]
        lo, hi = min(raws), max(raws)
        if hi == lo:
            return [50.0] * len(raws)
        return [((r - lo) / (hi - lo)) * 100 for r in raws]

    @staticmethod
    def _classify_risk(
        emp: Employee, raw: float, risk_score: float
    ) -> Tuple[RiskLevel, str]:
        reasons: List[str] = []

        if emp.delayed_tasks >= 3:
            reasons.append(f"{emp.delayed_tasks} delayed tasks")
        if emp.active_tasks >= 7:
            reasons.append(f"{emp.active_tasks} active tasks")
        if emp.availability_score <= 20:
            reasons.append(f"availability only {emp.availability_score}%")
        if emp.task_complexity_distribution.critical > 0:
            reasons.append(
                f"{emp.task_complexity_distribution.critical} critical-complexity task(s)"
            )
        if emp.past_success_rate < 0.70:
            reasons.append(f"low success rate ({emp.past_success_rate:.0%})")

        for level, (lo, hi) in RISK_THRESHOLDS.items():
            if lo <= risk_score < hi:
                reason = "; ".join(reasons) if reasons else "within normal operating range"
                return level, reason

        return RiskLevel.HIGH, "; ".join(reasons)

    @staticmethod
    def _is_underutilized(emp: Employee, risk_score: float) -> bool:
        return (
            risk_score < UNDERUTILIZED_SCORE_THRESHOLD
            and emp.availability_score >= 70
            and emp.active_tasks <= 2
        )

    @staticmethod
    def _is_bottleneck(emp: Employee) -> bool:
        if emp.active_tasks == 0:
            return False
        ratio = emp.delayed_tasks / emp.active_tasks
        return ratio >= BOTTLENECK_DELAYED_RATIO


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _effective_complexity_weight(dist: TaskComplexityDistribution) -> float:
    """
    Weighted average complexity across the employee's task mix.
    Defaults to 1.0 (medium) when no distribution is provided.
    """
    total = dist.low + dist.medium + dist.high + dist.critical
    if total == 0:
        return COMPLEXITY_WEIGHTS["medium"]

    weighted = (
        dist.low * COMPLEXITY_WEIGHTS["low"]
        + dist.medium * COMPLEXITY_WEIGHTS["medium"]
        + dist.high * COMPLEXITY_WEIGHTS["high"]
        + dist.critical * COMPLEXITY_WEIGHTS["critical"]
    )
    return weighted / total
