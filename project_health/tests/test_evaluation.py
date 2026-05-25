"""
tests/test_evaluation.py
Unit tests for all three scoring layers — no external I/O required.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.domain import (
    Deliverable,
    Goal,
    Priority,
    Project,
    ProjectNote,
    Requirement,
    RiskLevel,
    Task,
    TaskStatus,
)
from app.services.health_service import compute_health_score
from app.services.drift_service import detect_drift, predict_risk


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_project(
    n_tasks: int = 5,
    n_completed: int = 3,
    with_delays: bool = False,
) -> Project:
    today = date.today()
    goals = [
        Goal(id="g1", title="Core Features", weight=0.6),
        Goal(id="g2", title="Documentation", weight=0.4),
    ]
    requirements = [
        Requirement(
            requirement_id="r1",
            description="User authentication with OAuth2 and JWT tokens",
            weight=0.5,
            project_id="p1",
        ),
        Requirement(
            requirement_id="r2",
            description="Real-time dashboard with WebSocket updates",
            weight=0.5,
            project_id="p1",
        ),
    ]
    tasks = []
    for i in range(n_tasks):
        status = TaskStatus.COMPLETED if i < n_completed else TaskStatus.IN_PROGRESS
        deadline = (today - timedelta(days=3)) if (with_delays and i >= n_completed) else (today + timedelta(days=7))
        tasks.append(Task(
            id=f"t{i}",
            title=f"Task {i}",
            description=f"Implement feature component {i}",
            status=status,
            priority=Priority.HIGH if i % 2 == 0 else Priority.MEDIUM,
            goal_id="g1" if i < 3 else "g2",
            deadline=deadline,
            estimated_hours=8.0,
            actual_hours=10.0 if status == TaskStatus.COMPLETED else None,
            project_id="p1",
        ))

    return Project(
        id="p1",
        name="Test Project",
        description="A comprehensive test project",
        goals=goals,
        requirements=requirements,
        tasks=tasks,
        deliverables=[
            Deliverable(
                id="d1",
                title="Auth Module",
                description="OAuth2 JWT authentication implementation",
                project_id="p1",
            )
        ],
        notes=[],
    )


# ─── Health Score Tests ───────────────────────────────────────────────────────

class TestHealthScore:

    def test_completion_rate_correct(self):
        project = make_project(n_tasks=5, n_completed=3)
        result = compute_health_score(project)
        assert result.completion_rate == pytest.approx(60.0, abs=0.1)

    def test_perfect_completion_high_score(self):
        project = make_project(n_tasks=4, n_completed=4)
        result = compute_health_score(project)
        assert result.health_score > 60.0

    def test_delays_penalise_score(self):
        no_delay = compute_health_score(make_project(n_tasks=5, n_completed=2, with_delays=False))
        with_delay = compute_health_score(make_project(n_tasks=5, n_completed=2, with_delays=True))
        assert with_delay.health_score < no_delay.health_score

    def test_delayed_tasks_listed(self):
        project = make_project(n_tasks=5, n_completed=2, with_delays=True)
        result = compute_health_score(project)
        assert len(result.delayed_tasks) > 0

    def test_score_bounded_0_to_100(self):
        project = make_project(n_tasks=10, n_completed=0, with_delays=True)
        result = compute_health_score(project)
        assert 0.0 <= result.health_score <= 100.0

    def test_goal_progress_computed(self):
        project = make_project(n_tasks=5, n_completed=3)
        result = compute_health_score(project)
        assert len(result.goal_details) == 2
        assert all(0.0 <= g.progress <= 1.0 for g in result.goal_details)

    def test_score_breakdown_keys(self):
        project = make_project(n_tasks=5, n_completed=3)
        result = compute_health_score(project)
        assert "goal_progress_contribution" in result.score_breakdown
        assert "delay_penalty" in result.score_breakdown

    def test_efficiency_score_with_data(self):
        project = make_project(n_tasks=5, n_completed=3)
        result = compute_health_score(project)
        # estimated=8, actual=10 → efficiency ratio = 0.8
        assert result.efficiency_score > 0.0


# ─── Drift Detection Tests ────────────────────────────────────────────────────

class TestDriftDetection:

    def _mock_alignment(self, scores: list[float]):
        from app.models.domain import (
            AlignmentScoreResult, RequirementAlignment, AlignmentAlert
        )
        req_details = []
        for i, score in enumerate(scores):
            alert = None
            if score == 0.0:
                alert = "drift_detected"
            elif score < 0.40:
                alert = "semantic_drift"
            req_details.append(RequirementAlignment(
                requirement_id=f"r{i}",
                description=f"Requirement {i}",
                weight=1.0 / len(scores),
                alignment_score=score,
                matched_task_ids=[],
                alert=alert,
            ))
        return AlignmentScoreResult(
            project_id="p1",
            alignment_score=sum(scores) / len(scores) * 100,
            requirement_details=req_details,
            alerts=[],
            orphan_task_ids=[],
        )

    def test_no_drift_high_alignment(self):
        project = make_project()
        alignment = self._mock_alignment([0.85, 0.90])
        report = detect_drift(project, alignment)
        assert not report.drift_detected

    def test_drift_detected_low_alignment(self):
        project = make_project()
        alignment = self._mock_alignment([0.20, 0.90])
        report = detect_drift(project, alignment)
        assert report.drift_detected
        assert any(s.drift_type == "semantic_drift" for s in report.signals)

    def test_critical_drift_on_no_coverage(self):
        project = make_project()
        alignment = self._mock_alignment([0.0, 0.85])
        report = detect_drift(project, alignment)
        critical = [s for s in report.signals if s.severity == RiskLevel.CRITICAL]
        assert len(critical) >= 1

    def test_orphan_tasks_flagged(self):
        from app.models.domain import AlignmentScoreResult
        project = make_project()
        alignment = self._mock_alignment([0.80, 0.80])
        alignment.orphan_task_ids = ["t_orphan_1", "t_orphan_2"]
        report = detect_drift(project, alignment)
        assert report.drift_detected
        assert any(s.drift_type == "orphan_tasks" for s in report.signals)


# ─── Risk Forecast Tests ──────────────────────────────────────────────────────

class TestRiskForecast:

    def _health(self, score: float):
        from app.models.domain import HealthScoreResult
        return HealthScoreResult(
            project_id="p1",
            health_score=score,
            completion_rate=50.0,
            goal_progress=50.0,
            efficiency_score=80.0,
            delay_score=0.0,
            delayed_tasks=[],
            goal_details=[],
            score_breakdown={},
        )

    def _alignment(self, score: float):
        from app.models.domain import AlignmentScoreResult
        return AlignmentScoreResult(
            project_id="p1",
            alignment_score=score,
            requirement_details=[],
            alerts=[],
            orphan_task_ids=[],
        )

    def test_low_risk_healthy_project(self):
        project = make_project(n_tasks=5, n_completed=5)
        forecast = predict_risk(project, self._health(90), self._alignment(90))
        assert forecast.overall_risk in (RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_high_risk_unhealthy_project(self):
        project = make_project(n_tasks=5, n_completed=0, with_delays=True)
        forecast = predict_risk(project, self._health(20), self._alignment(30))
        assert forecast.overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_failure_risk_bounded(self):
        project = make_project()
        forecast = predict_risk(project, self._health(50), self._alignment(50))
        assert 0.0 <= forecast.predicted_failure_risk <= 1.0

    def test_risk_drivers_populated_for_bad_project(self):
        project = make_project(n_tasks=5, n_completed=0, with_delays=True)
        forecast = predict_risk(project, self._health(15), self._alignment(20))
        assert len(forecast.risk_drivers) > 0
