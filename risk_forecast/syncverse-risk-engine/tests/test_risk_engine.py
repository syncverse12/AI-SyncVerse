"""
Test suite for the AI Risk Intelligence Engine.

Tests cover:
  - Rule-based scoring
  - Score composition
  - Alert cooldown & dedup
  - Severity mapping
  - WebSocket message format
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.schemas import (
    CategoryRiskScore,
    LiveProjectMetrics,
    ProjectRequirements,
    RiskCategory,
    RiskSeverity,
    TeamMember,
    TechStack,
)
from app.scoring.risk_engine import (
    LiveRuleScorer,
    PreProjectRuleScorer,
    RiskScoringEngine,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_project(
    *,
    deadline_days: int = 90,
    estimated_hours: float = 800,
    team_workload: float = 50,
    requirement_completeness: float = 90,
    required_skills: list[str] | None = None,
    team_skills: list[str] | None = None,
    dependencies: int = 2,
    client_responsiveness: float = 8.0,
    infrastructure_ready: bool = True,
) -> ProjectRequirements:
    now = datetime.now(timezone.utc)
    return ProjectRequirements(
        project_id=uuid4(),
        project_name="Test Project",
        description="A test project",
        client_name="TestCo",
        start_date=now + timedelta(days=7),
        deadline=now + timedelta(days=7 + deadline_days),
        estimated_hours=estimated_hours,
        budget_usd=100_000,
        team=[
            TeamMember(
                name="Dev A",
                role="Backend",
                skills=team_skills or ["Python", "FastAPI"],
                current_workload_pct=team_workload,
                seniority_years=3,
            )
        ],
        tech_stack=TechStack(languages=["Python"], frameworks=["FastAPI"]),
        required_skills=required_skills or ["Python"],
        requirement_completeness_pct=requirement_completeness,
        dependencies_count=dependencies,
        client_responsiveness=client_responsiveness,
        infrastructure_ready=infrastructure_ready,
    )


def make_live_metrics(
    *,
    velocity_ratio: float = 1.0,
    overdue_ratio: float = 0.0,
    overtime: float = 0.0,
    client_alignment: float = 9.0,
    deployment_failures: int = 0,
    sentiment: float = 0.1,
) -> LiveProjectMetrics:
    total_tasks = 50
    return LiveProjectMetrics(
        project_id=uuid4(),
        sprint_velocity=velocity_ratio * 40,
        planned_velocity=40,
        sprint_completion_rate=1 - overdue_ratio,
        overdue_tasks=int(total_tasks * overdue_ratio),
        total_tasks=total_tasks,
        blocked_tasks=0,
        team_overtime_hours_avg=overtime,
        client_alignment_score=client_alignment,
        deployment_failures_last_30d=deployment_failures,
        negative_sentiment_score=sentiment,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Pre-Project Rule Scoring Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPreProjectRuleScorer:
    scorer = PreProjectRuleScorer()

    def test_clean_project_has_low_risk(self):
        req = make_project()
        scores = self.scorer.score(req)
        assert scores.technical < 0.2
        assert scores.timeline < 0.3
        assert scores.human < 0.2

    def test_skill_gap_raises_technical_risk(self):
        req = make_project(
            required_skills=["Python", "Kubernetes", "GraphQL", "Rust"],
            team_skills=["Python"],
        )
        scores = self.scorer.score(req)
        assert scores.technical > 0.4
        assert any("Missing" in f for f in scores.reasons[RiskCategory.TECHNICAL.value])

    def test_overloaded_team_raises_human_risk(self):
        req = make_project(team_workload=85)
        scores = self.scorer.score(req)
        assert scores.human > 0.3
        assert any("capacity" in f.lower() for f in scores.reasons[RiskCategory.HUMAN.value])

    def test_aggressive_timeline_raises_timeline_risk(self):
        # 200 hours in 10 days = 20h/day → extreme
        req = make_project(deadline_days=10, estimated_hours=200)
        scores = self.scorer.score(req)
        assert scores.timeline > 0.5

    def test_incomplete_requirements_raise_delivery_risk(self):
        req = make_project(requirement_completeness=40)
        scores = self.scorer.score(req)
        assert scores.delivery > 0.35

    def test_low_client_responsiveness_raises_client_risk(self):
        req = make_project(client_responsiveness=3.0)
        scores = self.scorer.score(req)
        assert scores.client > 0.3

    def test_infrastructure_not_ready_raises_infra_risk(self):
        req = make_project(infrastructure_ready=False)
        scores = self.scorer.score(req)
        assert scores.infrastructure > 0.3

    def test_high_dependency_count_raises_technical_risk(self):
        req = make_project(dependencies=15)
        scores = self.scorer.score(req)
        assert scores.technical > 0.2

    def test_all_scores_clamped_between_0_and_1(self):
        # Worst possible project
        req = make_project(
            deadline_days=5,
            estimated_hours=1000,
            team_workload=100,
            requirement_completeness=10,
            required_skills=["Python", "Rust", "Kubernetes", "ML", "DevOps"],
            team_skills=[],
            dependencies=20,
            client_responsiveness=1.0,
            infrastructure_ready=False,
        )
        scores = self.scorer.score(req)
        for field in ["technical", "timeline", "budget", "human", "delivery", "client", "infrastructure"]:
            val = getattr(scores, field)
            assert 0.0 <= val <= 1.0, f"{field} out of range: {val}"


# ══════════════════════════════════════════════════════════════════════════════
# Live Rule Scoring Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestLiveRuleScorer:
    scorer = LiveRuleScorer()

    def test_healthy_project_has_low_risk(self):
        metrics = make_live_metrics(velocity_ratio=1.05, overdue_ratio=0.05)
        scores = self.scorer.score(metrics)
        assert scores.timeline < 0.2
        assert scores.human < 0.2

    def test_low_velocity_raises_timeline_risk(self):
        metrics = make_live_metrics(velocity_ratio=0.45)
        scores = self.scorer.score(metrics)
        assert scores.timeline > 0.5

    def test_high_overtime_raises_human_risk(self):
        metrics = make_live_metrics(overtime=20)
        scores = self.scorer.score(metrics)
        assert scores.human > 0.4

    def test_low_client_alignment_raises_client_risk(self):
        metrics = make_live_metrics(client_alignment=3.5)
        scores = self.scorer.score(metrics)
        assert scores.client > 0.4

    def test_deployment_failures_raise_technical_risk(self):
        metrics = make_live_metrics(deployment_failures=6)
        scores = self.scorer.score(metrics)
        assert scores.technical > 0.3

    def test_negative_sentiment_raises_human_risk(self):
        metrics = make_live_metrics(sentiment=0.8)
        scores = self.scorer.score(metrics)
        assert scores.human > 0.25


# ══════════════════════════════════════════════════════════════════════════════
# Composite Scoring Engine Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRiskScoringEngine:
    engine = RiskScoringEngine()

    def _make_rule_scores(self, **kwargs):
        from app.scoring.risk_engine import PreProjectRuleScores, RiskCategory
        defaults = dict(
            technical=0.1, timeline=0.1, budget=0.0,
            human=0.1, delivery=0.1, client=0.1,
            infrastructure=0.0,
            reasons={c.value: [] for c in RiskCategory},
        )
        defaults.update(kwargs)
        return PreProjectRuleScores(**defaults)

    def test_low_scores_produce_low_overall(self):
        rule = self._make_rule_scores()
        breakdown = self.engine.compute_from_rules(rule)
        assert breakdown.overall < 0.3
        assert breakdown.severity == RiskSeverity.LOW

    def test_high_scores_produce_high_overall(self):
        rule = self._make_rule_scores(
            technical=0.8, timeline=0.9, human=0.7, delivery=0.8
        )
        breakdown = self.engine.compute_from_rules(rule)
        assert breakdown.overall > 0.6
        assert breakdown.severity in (RiskSeverity.HIGH, RiskSeverity.CRITICAL)

    def test_ml_adjustment_increases_score(self):
        rule = self._make_rule_scores(timeline=0.4)
        base = self.engine.compute_from_rules(rule, ml_adjustment=0.0)
        adjusted = self.engine.compute_from_rules(rule, ml_adjustment=0.3)
        assert adjusted.overall > base.overall

    def test_ai_calibration_blends_into_score(self):
        rule = self._make_rule_scores(timeline=0.3)
        base = self.engine.compute_from_rules(rule, ai_calibration=0.0)
        calibrated = self.engine.compute_from_rules(rule, ai_calibration=0.8)
        # High AI calibration should pull score up
        assert calibrated.overall > base.overall

    def test_categories_sorted_by_score_descending(self):
        rule = self._make_rule_scores(technical=0.8, timeline=0.2, human=0.5)
        breakdown = self.engine.compute_from_rules(rule)
        scores = [c.score for c in breakdown.categories]
        assert scores == sorted(scores, reverse=True)

    def test_overall_score_clamped_to_1(self):
        rule = self._make_rule_scores(
            technical=1.0, timeline=1.0, human=1.0,
            delivery=1.0, client=1.0, infrastructure=1.0,
        )
        breakdown = self.engine.compute_from_rules(rule, ml_adjustment=1.0, ai_calibration=1.0)
        assert breakdown.overall <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Severity Mapping Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSeverityMapping:
    def test_severity_boundaries(self):
        from app.scoring.risk_engine import _severity
        from app.core.config import settings

        assert _severity(0.1) == RiskSeverity.LOW
        assert _severity(settings.alert_threshold_medium) == RiskSeverity.MEDIUM
        assert _severity(settings.alert_threshold_high) == RiskSeverity.HIGH
        assert _severity(settings.alert_threshold_critical) == RiskSeverity.CRITICAL
        assert _severity(1.0) == RiskSeverity.CRITICAL


# ══════════════════════════════════════════════════════════════════════════════
# Alert Engine Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAlertEngine:
    @pytest.mark.asyncio
    async def test_no_alert_when_score_unchanged(self):
        from app.alerts.alert_engine import AlertEngine

        redis = AsyncMock()
        redis.exists.return_value = False
        orchestrator = AsyncMock()
        alert_repo = AsyncMock()

        engine = AlertEngine(redis, orchestrator, alert_repo)

        category = CategoryRiskScore(
            category=RiskCategory.TIMELINE,
            score=0.6,
            severity=RiskSeverity.MEDIUM,
            contributing_factors=["Test factor"],
            weight=0.25,
        )

        # Same score — delta = 0 → no alert
        alerts = await engine.evaluate(
            project_id=uuid4(),
            current_categories=[category],
            previous_categories=[category],
        )
        assert alerts == []

    @pytest.mark.asyncio
    async def test_alert_fired_on_significant_increase(self):
        from app.alerts.alert_engine import AlertEngine

        redis = AsyncMock()
        redis.exists.return_value = False  # No cooldown, no dedup
        orchestrator = AsyncMock()
        orchestrator.complete_json.return_value = {"ai_insight": "Test insight"}
        alert_repo = AsyncMock()

        engine = AlertEngine(redis, orchestrator, alert_repo)

        project_id = uuid4()
        prev = CategoryRiskScore(
            category=RiskCategory.HUMAN,
            score=0.35,
            severity=RiskSeverity.LOW,
            contributing_factors=[],
            weight=0.20,
        )
        curr = CategoryRiskScore(
            category=RiskCategory.HUMAN,
            score=0.75,  # +40% jump
            severity=RiskSeverity.HIGH,
            contributing_factors=["Overtime 20h/week"],
            weight=0.20,
        )

        alerts = await engine.evaluate(
            project_id=project_id,
            current_categories=[curr],
            previous_categories=[prev],
        )

        assert len(alerts) == 1
        assert alerts[0].severity == RiskSeverity.HIGH
        assert alerts[0].delta == pytest.approx(0.40, abs=0.01)
        alert_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_cooldown_suppresses_alert(self):
        from app.alerts.alert_engine import AlertEngine

        redis = AsyncMock()
        redis.exists.return_value = True  # In cooldown

        engine = AlertEngine(redis, AsyncMock(), AsyncMock())

        prev = CategoryRiskScore(
            category=RiskCategory.TECHNICAL,
            score=0.3,
            severity=RiskSeverity.LOW,
            contributing_factors=[],
            weight=0.20,
        )
        curr = CategoryRiskScore(
            category=RiskCategory.TECHNICAL,
            score=0.8,
            severity=RiskSeverity.HIGH,
            contributing_factors=["Many failures"],
            weight=0.20,
        )

        alerts = await engine.evaluate(
            project_id=uuid4(),
            current_categories=[curr],
            previous_categories=[prev],
        )

        assert alerts == []  # Suppressed by cooldown


# ══════════════════════════════════════════════════════════════════════════════
# Schema Validation Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaValidation:
    def test_deadline_must_be_after_start(self):
        from pydantic import ValidationError
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            make_project.__wrapped__ if hasattr(make_project, "__wrapped__") else None
            ProjectRequirements(
                project_id=uuid4(),
                project_name="Bad",
                description="desc",
                client_name="client",
                start_date=now + timedelta(days=10),
                deadline=now + timedelta(days=5),  # before start!
                estimated_hours=100,
                budget_usd=10000,
                team=[],
                tech_stack=TechStack(),
            )

    def test_live_metrics_score_bounds(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LiveProjectMetrics(
                project_id=uuid4(),
                sprint_velocity=40,
                planned_velocity=40,
                sprint_completion_rate=1.5,  # > 1 — invalid
                overdue_tasks=0,
                total_tasks=10,
                blocked_tasks=0,
            )
