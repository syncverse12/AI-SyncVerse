"""Unit tests for the rule-based Risk Engine — the most defense-critical layer."""

import pytest
from app.risk_engine.rules import (
    calculate_timeline_risk, calculate_resource_risk, calculate_productivity_risk,
    calculate_dependency_risk, calculate_communication_risk, calculate_confirmed_risk_component,
)


def test_timeline_risk_high_when_overdue_and_close_deadline():
    raw = {"days_remaining": 2, "overdue_milestones_count": 3, "total_milestones": 4}
    result = calculate_timeline_risk(raw)
    assert result.score > 60
    assert result.severity in ("High", "Critical")
    assert result.source == "calculated"


def test_timeline_risk_low_when_plenty_of_time_and_no_overdue():
    raw = {"days_remaining": 60, "overdue_milestones_count": 0, "total_milestones": 5}
    result = calculate_timeline_risk(raw)
    assert result.score < 35


def test_timeline_risk_low_confidence_when_no_data():
    result = calculate_timeline_risk({"days_remaining": None})
    assert result.confidence <= 0.3


def test_resource_risk_scales_with_overload():
    low = calculate_resource_risk({"avg_workload_ratio": 0.5, "overloaded_members_count": 0, "team_size": 5})
    high = calculate_resource_risk({"avg_workload_ratio": 1.8, "overloaded_members_count": 4, "team_size": 5})
    assert high.score > low.score


def test_productivity_risk_penalizes_zero_velocity():
    result = calculate_productivity_risk({"progress_pct": 30, "avg_task_age_days": 20, "velocity_last_period": 0})
    assert result.score > 30


def test_dependency_risk_zero_when_no_blocked_tasks():
    result = calculate_dependency_risk({"blocked_tasks_count": 0}, total_tasks=10)
    assert result.score == 0.0
    assert result.severity == "Low"


def test_dependency_risk_scales_with_blocked_ratio():
    result = calculate_dependency_risk({"blocked_tasks_count": 5}, total_tasks=10)
    assert result.score > 0


def test_communication_risk_higher_for_high_priority_with_few_meetings():
    low_priority = calculate_communication_risk({"meeting_count": 1}, project_priority="Low")
    high_priority = calculate_communication_risk({"meeting_count": 1}, project_priority="Critical")
    assert high_priority.score >= low_priority.score


def test_confirmed_risk_reflects_open_manual_risks():
    raw = {"confirmed_risk_load": 8, "open_confirmed_risks": [1, 2]}
    result = calculate_confirmed_risk_component(raw)
    assert result.score > 0
    assert result.confidence >= 0.9  # ground truth data, high confidence
