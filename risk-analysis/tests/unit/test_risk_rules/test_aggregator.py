"""Unit tests for weighted Overall Risk aggregation."""

from app.risk_engine.aggregator import aggregate_overall_risk
from app.schemas.report_schema import RiskCategory


def _cat(name, score, confidence=0.8):
    return RiskCategory(
        name=name, score=score, severity="Medium", source="calculated",
        confidence=confidence, reason="test", used_metrics=[],
    )


def test_overall_risk_is_bounded_0_100():
    categories = [_cat("Timeline Risk", 90), _cat("Resource Risk", 95), _cat("Productivity Risk", 100)]
    result = aggregate_overall_risk(categories)
    assert 0 <= result.score <= 100


def test_overall_risk_low_when_all_categories_healthy():
    categories = [
        _cat("Timeline Risk", 10), _cat("Resource Risk", 5), _cat("Productivity Risk", 10),
        _cat("Communication Risk", 5), _cat("Budget Risk", 10),
    ]
    result = aggregate_overall_risk(categories)
    assert result.score < 35
    assert result.level == "Low"


def test_severe_dependency_risk_boosts_overall_score():
    healthy = [_cat("Timeline Risk", 10), _cat("Resource Risk", 10)]
    with_severe_blocker = healthy + [_cat("Dependency Risk", 95)]
    healthy_result = aggregate_overall_risk(healthy)
    boosted_result = aggregate_overall_risk(with_severe_blocker)
    assert boosted_result.score >= healthy_result.score
