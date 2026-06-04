"""
Risk Scoring Engine — modular, rule-based + ML-weighted scoring.

Architecture:
  RiskScoringEngine
    ├── RuleBasedScorer   (fast heuristics, runs always)
    ├── MLScorer          (model predictions, runs async)
    └── CompositeScorer   (merges rule + ML + AI scores)

All weights are configurable via settings — no magic numbers in logic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import (
    CategoryRiskScore,
    LiveProjectMetrics,
    ProjectRequirements,
    RiskCategory,
    RiskScoreBreakdown,
    RiskSeverity,
)

logger = get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _severity(score: float) -> RiskSeverity:
    """Map a 0–1 score to a severity label."""
    if score >= settings.alert_threshold_critical:
        return RiskSeverity.CRITICAL
    if score >= settings.alert_threshold_high:
        return RiskSeverity.HIGH
    if score >= settings.alert_threshold_medium:
        return RiskSeverity.MEDIUM
    return RiskSeverity.LOW


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


# ══════════════════════════════════════════════════════════════════════════════
# Pre-Project Rule-Based Scorer
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PreProjectRuleScores:
    technical: float
    timeline: float
    budget: float
    human: float
    delivery: float
    client: float
    infrastructure: float
    reasons: dict[str, list[str]]  # category → contributing factors


class PreProjectRuleScorer:
    """
    Fast heuristic scorer for pre-project risk assessment.
    Scores are 0.0 (no risk) → 1.0 (maximum risk).
    """

    def score(self, req: ProjectRequirements) -> PreProjectRuleScores:
        reasons: dict[str, list[str]] = {c.value: [] for c in RiskCategory}

        technical = self._technical(req, reasons)
        timeline = self._timeline(req, reasons)
        budget = self._budget(req, reasons)
        human = self._human(req, reasons)
        delivery = self._delivery(req, reasons)
        client = self._client(req, reasons)
        infrastructure = self._infrastructure(req, reasons)

        return PreProjectRuleScores(
            technical=technical,
            timeline=timeline,
            budget=budget,
            human=human,
            delivery=delivery,
            client=client,
            infrastructure=infrastructure,
            reasons=reasons,
        )

    def _technical(self, req: ProjectRequirements, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.TECHNICAL.value]

        # Skill gap analysis
        team_skills = {s.lower() for m in req.team for s in m.skills}
        missing = [s for s in req.required_skills if s.lower() not in team_skills]
        if missing:
            gap_ratio = len(missing) / max(len(req.required_skills), 1)
            score += gap_ratio * 0.5
            factors.append(f"Missing skills: {', '.join(missing[:5])}")

        # Dependency complexity
        if req.dependencies_count > 10:
            score += 0.2
            factors.append(f"High dependency count ({req.dependencies_count})")
        elif req.dependencies_count > 5:
            score += 0.1
            factors.append(f"Moderate dependencies ({req.dependencies_count})")

        # Third-party integrations
        if req.third_party_integrations_count > 5:
            score += 0.2
            factors.append(
                f"Complex third-party integrations ({req.third_party_integrations_count})"
            )
        elif req.third_party_integrations_count > 2:
            score += 0.1

        return _clamp(score)

    def _timeline(self, req: ProjectRequirements, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.TIMELINE.value]

        now = datetime.now(timezone.utc)
        days_total = (req.deadline - req.start_date).days
        hours_per_day = req.estimated_hours / max(days_total, 1)

        # Very aggressive timeline: > 10 hrs/day equivalent
        if hours_per_day > 10:
            score += 0.5
            factors.append(
                f"Timeline requires {hours_per_day:.1f}h/day — unsustainable"
            )
        elif hours_per_day > 8:
            score += 0.25
            factors.append(
                f"Tight timeline: {hours_per_day:.1f}h/day capacity required"
            )

        # Short total runway
        if days_total < 14:
            score += 0.3
            factors.append(f"Very short project runway ({days_total} days)")
        elif days_total < 30:
            score += 0.1

        # Near-term deadline
        days_until_start = (req.start_date - now).days
        if days_until_start < 7:
            score += 0.2
            factors.append("Project starts in less than 7 days — limited prep time")

        return _clamp(score)

    def _budget(self, req: ProjectRequirements, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.BUDGET.value]

        team_size = len(req.team)
        # Rough hourly cost estimate (avg $80/hr blended)
        estimated_cost = req.estimated_hours * 80
        if estimated_cost > req.budget_usd * 1.2:
            score += 0.5
            factors.append(
                f"Estimated cost (${estimated_cost:,.0f}) likely exceeds budget "
                f"(${req.budget_usd:,.0f})"
            )
        elif estimated_cost > req.budget_usd * 0.9:
            score += 0.2
            factors.append("Budget is tight relative to estimated hours")

        # Small budget for large team
        budget_per_dev = req.budget_usd / max(team_size, 1)
        if budget_per_dev < 5000:
            score += 0.2
            factors.append(
                f"Low per-developer budget (${budget_per_dev:,.0f}) signals scope risk"
            )

        return _clamp(score)

    def _human(self, req: ProjectRequirements, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.HUMAN.value]

        overloaded = [m for m in req.team if m.current_workload_pct > 70]
        if overloaded:
            ratio = len(overloaded) / len(req.team)
            score += ratio * 0.5
            names = ", ".join(m.name for m in overloaded[:3])
            factors.append(f"Team members at >70% capacity: {names}")

        # Small team for large project
        if len(req.team) < 2 and req.estimated_hours > 200:
            score += 0.3
            factors.append("Solo contributor risk for a multi-hundred-hour project")

        # Low seniority for complex work
        avg_seniority = sum(m.seniority_years for m in req.team) / max(len(req.team), 1)
        if avg_seniority < 2 and req.dependencies_count > 5:
            score += 0.2
            factors.append(
                f"Junior-heavy team (avg {avg_seniority:.1f}yr) for complex project"
            )

        return _clamp(score)

    def _delivery(self, req: ProjectRequirements, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.DELIVERY.value]

        # Requirement incompleteness
        incompleteness = (100 - req.requirement_completeness_pct) / 100
        score += incompleteness * 0.6
        if req.requirement_completeness_pct < 60:
            factors.append(
                f"Requirements only {req.requirement_completeness_pct:.0f}% complete — "
                "high scope creep risk"
            )
        elif req.requirement_completeness_pct < 80:
            factors.append("Incomplete requirements increase rework probability")

        if not req.has_clear_requirements:
            score += 0.2
            factors.append("Requirements flagged as unclear by stakeholders")

        return _clamp(score)

    def _client(self, req: ProjectRequirements, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.CLIENT.value]

        if req.client_responsiveness < 5:
            score += 0.4
            factors.append(
                f"Low client responsiveness score ({req.client_responsiveness}/10)"
            )
        elif req.client_responsiveness < 7:
            score += 0.2
            factors.append("Below-average client responsiveness expected")

        return _clamp(score)

    def _infrastructure(self, req: ProjectRequirements, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.INFRASTRUCTURE.value]

        if not req.infrastructure_ready:
            score += 0.4
            factors.append("Infrastructure not ready at project start")

        return _clamp(score)


# ══════════════════════════════════════════════════════════════════════════════
# Live Monitoring Rule Scorer
# ══════════════════════════════════════════════════════════════════════════════

class LiveRuleScorer:
    """Scores a live metrics snapshot against risk categories."""

    def score(self, metrics: LiveProjectMetrics) -> PreProjectRuleScores:
        reasons: dict[str, list[str]] = {c.value: [] for c in RiskCategory}

        technical = self._technical(metrics, reasons)
        timeline = self._timeline(metrics, reasons)
        budget = 0.0  # budget tracked separately via finance service
        human = self._human(metrics, reasons)
        delivery = self._delivery(metrics, reasons)
        client = self._client(metrics, reasons)
        infrastructure = self._infrastructure(metrics, reasons)

        return PreProjectRuleScores(
            technical=technical,
            timeline=timeline,
            budget=budget,
            human=human,
            delivery=delivery,
            client=client,
            infrastructure=infrastructure,
            reasons=reasons,
        )

    def _technical(self, m: LiveProjectMetrics, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.TECHNICAL.value]

        if m.deployment_failures_last_30d > 3:
            score += 0.4
            factors.append(f"{m.deployment_failures_last_30d} deployment failures this month")

        if m.qa_failure_rate > 0.3:
            score += 0.3
            factors.append(f"QA failure rate at {m.qa_failure_rate*100:.0f}%")

        if m.pr_avg_review_hours > 48:
            score += 0.2
            factors.append(f"PRs averaging {m.pr_avg_review_hours:.0f}h in review — bottleneck")

        if m.github_commits_last_7d < 3:
            score += 0.2
            factors.append("Low GitHub activity — possible blocker or disengagement")

        return _clamp(score)

    def _timeline(self, m: LiveProjectMetrics, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.TIMELINE.value]

        velocity_ratio = m.sprint_velocity / max(m.planned_velocity, 0.01)
        if velocity_ratio < 0.6:
            score += 0.5
            factors.append(
                f"Sprint velocity at {velocity_ratio*100:.0f}% of plan — severe delay risk"
            )
        elif velocity_ratio < 0.8:
            score += 0.25
            factors.append(f"Sprint velocity at {velocity_ratio*100:.0f}% of plan")

        overdue_ratio = m.overdue_tasks / max(m.total_tasks, 1)
        if overdue_ratio > 0.3:
            score += 0.3
            factors.append(
                f"{overdue_ratio*100:.0f}% tasks overdue ({m.overdue_tasks}/{m.total_tasks})"
            )

        if m.blocked_tasks > 5:
            score += 0.2
            factors.append(f"{m.blocked_tasks} blocked tasks creating cascade risk")

        return _clamp(score)

    def _human(self, m: LiveProjectMetrics, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.HUMAN.value]

        if m.team_overtime_hours_avg > 15:
            score += 0.5
            factors.append(
                f"Average overtime: {m.team_overtime_hours_avg:.0f}h/week — burnout imminent"
            )
        elif m.team_overtime_hours_avg > 8:
            score += 0.25
            factors.append(f"Sustained overtime: {m.team_overtime_hours_avg:.0f}h/week average")

        if m.negative_sentiment_score > 0.5:
            score += 0.3
            factors.append(
                f"Negative communication sentiment at {m.negative_sentiment_score*100:.0f}%"
            )

        if m.task_reassignment_count > 5:
            score += 0.2
            factors.append(
                f"{m.task_reassignment_count} task reassignments — instability signal"
            )

        if m.team_absences_count > 2:
            score += 0.15
            factors.append(f"{m.team_absences_count} team absences impacting velocity")

        return _clamp(score)

    def _delivery(self, m: LiveProjectMetrics, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.DELIVERY.value]

        completion = m.sprint_completion_rate
        if completion < 0.5:
            score += 0.5
            factors.append(f"Sprint completion at {completion*100:.0f}% — delivery at risk")
        elif completion < 0.75:
            score += 0.25

        return _clamp(score)

    def _client(self, m: LiveProjectMetrics, reasons: dict) -> float:
        score = 0.0
        factors = reasons[RiskCategory.CLIENT.value]

        if m.client_alignment_score < 5:
            score += 0.5
            factors.append(
                f"Client alignment score critically low ({m.client_alignment_score}/10)"
            )
        elif m.client_alignment_score < 7:
            score += 0.25
            factors.append(f"Declining client alignment ({m.client_alignment_score}/10)")

        if m.client_response_delay_hours > 48:
            score += 0.2
            factors.append(
                f"Client averaging {m.client_response_delay_hours:.0f}h response time"
            )

        if m.unresolved_client_feedback > 3:
            score += 0.2
            factors.append(f"{m.unresolved_client_feedback} unresolved client feedback items")

        return _clamp(score)

    def _infrastructure(self, m: LiveProjectMetrics, _: dict) -> float:
        # Infrastructure risk assessed from deployment failures in technical
        return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Composite Scorer
# ══════════════════════════════════════════════════════════════════════════════

class RiskScoringEngine:
    """
    Combines rule-based scores, ML predictions, and AI calibration
    into a final RiskScoreBreakdown.
    """

    CATEGORY_WEIGHTS: dict[RiskCategory, float] = {
        RiskCategory.TIMELINE: settings.risk_weight_deadline,
        RiskCategory.HUMAN: settings.risk_weight_workload,
        RiskCategory.TECHNICAL: settings.risk_weight_skill_gap,
        RiskCategory.CLIENT: settings.risk_weight_client_alignment,
        RiskCategory.DELIVERY: settings.risk_weight_inactivity,
        RiskCategory.INFRASTRUCTURE: settings.risk_weight_deployment_failure,
        RiskCategory.BUDGET: 0.10,
    }

    def compute_from_rules(
        self,
        rule_scores: PreProjectRuleScores,
        ml_adjustment: float = 0.0,
        ai_calibration: float = 0.0,
    ) -> RiskScoreBreakdown:
        """
        Final score formula:
          overall = Σ(category_score × weight)
                    × (1 + ml_adjustment)
                    × confidence_factor(ai_calibration)
        """
        categories: list[CategoryRiskScore] = []
        weighted_sum = 0.0
        total_weight = 0.0

        score_map = {
            RiskCategory.TECHNICAL: rule_scores.technical,
            RiskCategory.TIMELINE: rule_scores.timeline,
            RiskCategory.BUDGET: rule_scores.budget,
            RiskCategory.HUMAN: rule_scores.human,
            RiskCategory.DELIVERY: rule_scores.delivery,
            RiskCategory.CLIENT: rule_scores.client,
            RiskCategory.INFRASTRUCTURE: rule_scores.infrastructure,
        }

        for category, weight in self.CATEGORY_WEIGHTS.items():
            raw_score = score_map[category]
            adjusted = _clamp(raw_score + ml_adjustment * weight)

            categories.append(
                CategoryRiskScore(
                    category=category,
                    score=round(adjusted, 4),
                    severity=_severity(adjusted),
                    contributing_factors=rule_scores.reasons.get(category.value, []),
                    weight=weight,
                )
            )
            weighted_sum += adjusted * weight
            total_weight += weight

        overall = _clamp(weighted_sum / max(total_weight, 1))

        # ML bump — if model predicts higher risk, apply logarithmic blend
        if ml_adjustment > 0:
            overall = _clamp(overall * (1 + math.log1p(ml_adjustment) * 0.3))

        # AI calibration — direct override from LLM category sums
        if ai_calibration > 0:
            overall = _clamp(overall * 0.7 + ai_calibration * 0.3)

        confidence = 0.80 if ai_calibration == 0.0 else 0.92

        return RiskScoreBreakdown(
            overall=round(overall, 4),
            severity=_severity(overall),
            categories=sorted(categories, key=lambda c: c.score, reverse=True),
            confidence=confidence,
        )
