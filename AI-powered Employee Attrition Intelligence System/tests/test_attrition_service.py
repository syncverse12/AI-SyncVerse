"""
Unit tests for feature engineering and ML prediction pipeline.
Run: pytest tests/ -v
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, AsyncMock, patch

from app.feature_engineering.engineer import FeatureEngineer, RawEmployeeData
from app.explainability.shap_explainer import RecommendationEngine


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def sample_raw_data() -> RawEmployeeData:
    return RawEmployeeData(
        employee_id="EMP-TEST-001",
        age=32,
        department="Engineering",
        job_role="Software Engineer",
        job_level="Senior",
        monthly_income=9000.0,
        years_at_company=4.5,
        years_since_last_promotion=2.0,
        years_with_curr_manager=1.5,
        years_in_current_role=2.0,
        performance_rating=4.0,
        job_satisfaction=3.5,
        work_life_balance=2.0,
        environment_satisfaction=3.0,
        relationship_satisfaction=3.5,
        overtime_hours=50.0,
        standard_hours=160.0,
        attendance_rate=0.95,
        workload_score=8.0,
        team_health_score=6.0,
        collaboration_score=7.0,
        tasks_completed=25,
        tasks_assigned=30,
        missed_deadlines=3,
        overdue_task_ratio=0.10,
        leadership_score=6.5,
        promotion_velocity=2.5,
        training_hours=20.0,
    )


@pytest.fixture
def burnout_raw_data() -> RawEmployeeData:
    """Employee with obvious burnout signals."""
    return RawEmployeeData(
        employee_id="EMP-BURNOUT-001",
        age=29,
        department="Sales",
        job_role="Account Executive",
        job_level="Mid",
        monthly_income=3800.0,
        years_at_company=3.0,
        years_since_last_promotion=3.0,
        years_with_curr_manager=0.5,
        years_in_current_role=3.0,
        performance_rating=2.5,
        job_satisfaction=1.5,
        work_life_balance=1.5,
        environment_satisfaction=2.0,
        relationship_satisfaction=2.0,
        overtime_hours=90.0,
        standard_hours=160.0,
        attendance_rate=0.78,
        workload_score=9.5,
        team_health_score=3.5,
        collaboration_score=4.0,
        tasks_completed=12,
        tasks_assigned=30,
        missed_deadlines=10,
        overdue_task_ratio=0.35,
        leadership_score=3.0,
        promotion_velocity=4.0,
        training_hours=2.0,
    )


@pytest.fixture
def high_performer_data() -> RawEmployeeData:
    """Employee likely to be promoted."""
    return RawEmployeeData(
        employee_id="EMP-STAR-001",
        age=35,
        department="Engineering",
        job_role="Senior Engineer",
        job_level="Senior",
        monthly_income=11000.0,
        years_at_company=5.0,
        years_since_last_promotion=2.5,
        years_with_curr_manager=3.0,
        years_in_current_role=2.5,
        performance_rating=4.8,
        job_satisfaction=4.5,
        work_life_balance=4.0,
        environment_satisfaction=4.5,
        relationship_satisfaction=4.5,
        overtime_hours=15.0,
        standard_hours=160.0,
        attendance_rate=0.98,
        workload_score=6.0,
        team_health_score=8.5,
        collaboration_score=9.0,
        tasks_completed=45,
        tasks_assigned=47,
        missed_deadlines=0,
        overdue_task_ratio=0.0,
        leadership_score=8.5,
        promotion_velocity=2.0,
        training_hours=55.0,
    )


# ──────────────────────────────────────────────
# Feature Engineering Tests
# ──────────────────────────────────────────────

class TestFeatureEngineer:

    def test_engineer_returns_all_features(self, sample_raw_data):
        engineer = FeatureEngineer()
        features = engineer.engineer(sample_raw_data)
        assert features is not None
        assert features.overtime_ratio is not None
        assert features.burnout_signal is not None
        assert features.career_stagnation_score is not None
        assert features.engagement_score is not None

    def test_overtime_ratio_bounds(self, sample_raw_data):
        engineer = FeatureEngineer()
        features = engineer.engineer(sample_raw_data)
        assert 0.0 <= features.overtime_ratio <= 2.0

    def test_burnout_signal_higher_for_burned_out_employee(
        self, sample_raw_data, burnout_raw_data
    ):
        engineer = FeatureEngineer()
        normal = engineer.engineer(sample_raw_data)
        burned = engineer.engineer(burnout_raw_data)
        assert burned.burnout_signal > normal.burnout_signal

    def test_engagement_score_higher_for_star_performer(
        self, sample_raw_data, high_performer_data
    ):
        engineer = FeatureEngineer()
        normal = engineer.engineer(sample_raw_data)
        star = engineer.engineer(high_performer_data)
        assert star.engagement_score > normal.engagement_score

    def test_career_stagnation_score_bounds(self, sample_raw_data):
        engineer = FeatureEngineer()
        features = engineer.engineer(sample_raw_data)
        assert 0.0 <= features.career_stagnation_score <= 10.0

    def test_stability_score_bounds(self, sample_raw_data):
        engineer = FeatureEngineer()
        features = engineer.engineer(sample_raw_data)
        assert 0.0 <= features.stability_score <= 10.0

    def test_task_efficiency_bounds(self, sample_raw_data):
        engineer = FeatureEngineer()
        features = engineer.engineer(sample_raw_data)
        assert 0.0 <= features.task_efficiency_score <= 1.0

    def test_income_adequacy_mid_level(self):
        engineer = FeatureEngineer()
        raw = RawEmployeeData(
            employee_id="test",
            age=30,
            department="Engineering",
            job_role="Engineer",
            job_level="Mid",
            monthly_income=5000.0,  # exactly at baseline for Mid
            years_at_company=2.0,
            years_since_last_promotion=1.0,
            years_with_curr_manager=1.0,
        )
        features = engineer.engineer(raw)
        # Mid baseline = 5000, so ratio should be ~1.0
        assert abs(features.income_adequacy_ratio - 1.0) < 0.1

    def test_deadline_failure_rate_zero_when_no_missed(self, sample_raw_data):
        engineer = FeatureEngineer()
        sample_raw_data.missed_deadlines = 0
        features = engineer.engineer(sample_raw_data)
        assert features.deadline_failure_rate == 0.0

    def test_to_dict_has_all_keys(self, sample_raw_data):
        engineer = FeatureEngineer()
        features = engineer.engineer(sample_raw_data)
        d = features.to_dict()
        assert "burnout_signal" in d
        assert "engagement_score" in d
        assert "department" in d

    def test_to_numeric_dict_excludes_categoricals(self, sample_raw_data):
        engineer = FeatureEngineer()
        features = engineer.engineer(sample_raw_data)
        numeric = features.to_numeric_dict()
        assert "department" not in numeric
        assert "job_role" not in numeric
        assert "burnout_signal" in numeric


# ──────────────────────────────────────────────
# Recommendation Engine Tests
# ──────────────────────────────────────────────

class TestRecommendationEngine:

    def test_generates_high_priority_for_burnout(self):
        engine = RecommendationEngine()
        features = {
            "burnout_signal": 8.0,
            "overtime_ratio": 0.5,
            "work_life_balance": 1.5,
            "career_stagnation_score": 7.5,
            "income_adequacy_ratio": 0.75,
            "job_satisfaction": 3.5,
            "years_with_curr_manager": 2.0,
            "team_health_score": 7.0,
            "training_hours": 20.0,
            "missed_deadlines": 1,
        }
        recs = engine.generate(features)
        assert len(recs) > 0
        priorities = [r.priority for r in recs]
        assert "HIGH" in priorities

    def test_max_five_recommendations(self):
        engine = RecommendationEngine()
        features = {
            "burnout_signal": 9.0,
            "overtime_ratio": 0.6,
            "work_life_balance": 1.0,
            "career_stagnation_score": 9.0,
            "income_adequacy_ratio": 0.6,
            "job_satisfaction": 1.5,
            "years_with_curr_manager": 0.2,
            "team_health_score": 2.0,
            "training_hours": 0.0,
            "missed_deadlines": 10,
        }
        recs = engine.generate(features, top_n=5)
        assert len(recs) <= 5

    def test_no_recommendations_for_healthy_employee(self):
        engine = RecommendationEngine()
        features = {
            "burnout_signal": 2.0,
            "overtime_ratio": 0.05,
            "work_life_balance": 4.5,
            "career_stagnation_score": 2.0,
            "income_adequacy_ratio": 1.2,
            "job_satisfaction": 4.5,
            "years_with_curr_manager": 3.0,
            "team_health_score": 8.5,
            "training_hours": 50.0,
            "missed_deadlines": 0,
        }
        recs = engine.generate(features)
        assert len(recs) == 0

    def test_recommendations_sorted_by_priority(self):
        engine = RecommendationEngine()
        features = {
            "burnout_signal": 8.0,
            "overtime_ratio": 0.4,
            "work_life_balance": 2.0,
            "training_hours": 5.0,
            "career_stagnation_score": 3.0,
            "income_adequacy_ratio": 1.0,
            "job_satisfaction": 3.5,
            "years_with_curr_manager": 2.0,
            "team_health_score": 6.0,
            "missed_deadlines": 1,
        }
        recs = engine.generate(features)
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        for i in range(len(recs) - 1):
            assert priority_order[recs[i].priority] <= priority_order[recs[i + 1].priority]


# ──────────────────────────────────────────────
# Schema Validation Tests
# ──────────────────────────────────────────────

class TestSchemas:

    def test_attrition_response_valid(self):
        from datetime import datetime, timezone
        from app.schemas.schemas import AttritionPredictionResponse

        resp = AttritionPredictionResponse(
            employee_id="EMP-001",
            employee_name="John Doe",
            attrition_probability=0.72,
            risk_level="High",
            top_risk_factors=[],
            recommendations=[],
            explanation_summary="High risk due to burnout.",
            model_version="1.0.0",
            predicted_at=datetime.now(timezone.utc),
        )
        assert resp.risk_level == "High"
        assert resp.attrition_probability == 0.72

    def test_promotion_response_valid(self):
        from datetime import datetime, timezone
        from app.schemas.schemas import PromotionResponse

        resp = PromotionResponse(
            employee_id="EMP-001",
            promotion_readiness_score=78.5,
            promotion_recommended=True,
            recommended_role="Lead",
            promotion_reasoning=["Strong performance"],
            top_strengths=["Leadership"],
            development_areas=[],
            predicted_at=datetime.now(timezone.utc),
        )
        assert resp.promotion_recommended is True
        assert resp.recommended_role == "Lead"
