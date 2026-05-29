"""
SHAP Explainability Module.
Generates human-readable explanations for attrition predictions.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional

import numpy as np
import shap
from loguru import logger

from app.ml.predict import ModelRegistry
from app.ml.train import NUMERIC_FEATURES, CATEGORICAL_FEATURES, ALL_FEATURES
from app.schemas.schemas import RiskFactor, AttritionRecommendation


# Human-readable feature display names
FEATURE_DISPLAY_NAMES: Dict[str, str] = {
    "age": "Age",
    "monthly_income": "Monthly Income",
    "years_at_company": "Years at Company",
    "years_since_last_promotion": "Years Since Last Promotion",
    "years_with_curr_manager": "Years with Current Manager",
    "years_in_current_role": "Years in Current Role",
    "performance_rating": "Performance Rating",
    "job_satisfaction": "Job Satisfaction",
    "work_life_balance": "Work-Life Balance",
    "environment_satisfaction": "Environment Satisfaction",
    "relationship_satisfaction": "Relationship Satisfaction",
    "overtime_hours": "Overtime Hours",
    "attendance_rate": "Attendance Rate",
    "workload_score": "Workload Score",
    "team_health_score": "Team Health Score",
    "collaboration_score": "Collaboration Score",
    "tasks_completed": "Tasks Completed",
    "missed_deadlines": "Missed Deadlines",
    "overdue_task_ratio": "Overdue Task Ratio",
    "leadership_score": "Leadership Score",
    "promotion_velocity": "Promotion Velocity",
    "training_hours": "Training Hours",
    "department": "Department",
    "job_role": "Job Role",
    "job_level": "Job Level",
    "overtime_ratio": "Overtime Ratio",
    "deadline_failure_rate": "Deadline Failure Rate",
    "promotion_gap_years": "Promotion Gap (Years)",
    "workload_pressure_score": "Workload Pressure",
    "stability_score": "Stability Score",
    "burnout_signal": "Burnout Signal",
    "satisfaction_composite": "Overall Satisfaction",
    "performance_trend": "Performance Trend",
    "career_stagnation_score": "Career Stagnation",
    "income_adequacy_ratio": "Income Adequacy",
    "task_efficiency_score": "Task Efficiency",
    "engagement_score": "Employee Engagement",
}


class SHAPExplainer:
    """Generates SHAP-based explanations for attrition predictions."""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self._explainer: Optional[shap.TreeExplainer] = None

    def _get_explainer(self) -> shap.TreeExplainer:
        if self._explainer is None:
            raw_model = self.registry.attrition_model_raw
            if raw_model is None:
                logger.warning("Raw XGB model not available for SHAP. Using calibrated model.")
                raw_model = self.registry.attrition_model
            self._explainer = shap.TreeExplainer(raw_model)
        return self._explainer

    def explain(
        self, X_proc: np.ndarray, top_n: int = 6
    ) -> List[RiskFactor]:
        """
        Compute SHAP values and return top contributing risk factors.
        
        Args:
            X_proc: Preprocessed feature array (1 x n_features)
            top_n: Number of top factors to return
            
        Returns:
            List of RiskFactor sorted by absolute SHAP value
        """
        try:
            explainer = self._get_explainer()
            shap_values = explainer.shap_values(X_proc)

            # For binary classification, use class=1 (attrition) values
            if isinstance(shap_values, list):
                sv = shap_values[1][0]
            else:
                sv = shap_values[0]

            feature_impact = []
            for i, feature in enumerate(ALL_FEATURES):
                if i < len(sv):
                    impact = float(sv[i])
                    feature_impact.append((feature, impact))

            # Sort by absolute impact
            feature_impact.sort(key=lambda x: abs(x[1]), reverse=True)

            risk_factors = []
            for feature, impact in feature_impact[:top_n]:
                direction = "positive_risk" if impact > 0 else "negative_risk"
                risk_factors.append(
                    RiskFactor(
                        feature=feature,
                        display_name=FEATURE_DISPLAY_NAMES.get(feature, feature),
                        impact=round(impact, 4),
                        direction=direction,
                        description=self._generate_factor_description(feature, impact),
                    )
                )

            return risk_factors

        except Exception as exc:
            logger.error(f"SHAP explanation failed: {exc}")
            return self._fallback_explanation()

    def _generate_factor_description(self, feature: str, impact: float) -> str:
        """Generate a human-readable description for a SHAP factor."""
        sign = "significantly increases" if impact > 0.05 else (
            "slightly increases" if impact > 0 else
            "significantly decreases" if impact < -0.05 else
            "slightly decreases"
        )
        display = FEATURE_DISPLAY_NAMES.get(feature, feature)
        return f"{display} {sign} attrition risk."

    def _fallback_explanation(self) -> List[RiskFactor]:
        return []

    def generate_summary(self, risk_factors: List[RiskFactor], probability: float) -> str:
        """Generate a human-readable summary paragraph."""
        risk_label = (
            "high" if probability >= 0.65 else
            "moderate" if probability >= 0.35 else "low"
        )
        drivers = [f.display_name for f in risk_factors if f.impact > 0][:3]
        protectives = [f.display_name for f in risk_factors if f.impact < 0][:2]

        parts = [
            f"This employee shows {risk_label} attrition risk ({probability:.0%} probability)."
        ]
        if drivers:
            parts.append(
                f"Key risk drivers include: {', '.join(drivers)}."
            )
        if protectives:
            parts.append(
                f"Protective factors: {', '.join(protectives)}."
            )
        return " ".join(parts)


class RecommendationEngine:
    """Generates actionable retention recommendations based on risk factors."""

    RECOMMENDATION_RULES = [
        # (feature, condition_fn, recommendation)
        (
            "burnout_signal",
            lambda v: v > 6.0,
            AttritionRecommendation(
                priority="HIGH",
                category="wellbeing",
                action="Initiate immediate wellbeing check-in and consider temporary workload reduction.",
                expected_impact="Can reduce burnout-related attrition risk by 20-35%.",
            ),
        ),
        (
            "overtime_ratio",
            lambda v: v > 0.3,
            AttritionRecommendation(
                priority="HIGH",
                category="workload",
                action="Review and redistribute workload. Enforce overtime limits. Consider additional hiring.",
                expected_impact="Reducing excessive overtime is one of the strongest retention levers.",
            ),
        ),
        (
            "work_life_balance",
            lambda v: v < 2.5,
            AttritionRecommendation(
                priority="HIGH",
                category="wellbeing",
                action="Offer flexible working arrangements, remote work options, or compressed work weeks.",
                expected_impact="Work-life balance improvements are linked to 30%+ reduction in quit rates.",
            ),
        ),
        (
            "career_stagnation_score",
            lambda v: v > 6.0,
            AttritionRecommendation(
                priority="HIGH",
                category="career",
                action="Schedule a career development conversation. Explore promotion or lateral growth paths.",
                expected_impact="Career clarity reduces stagnation-driven attrition by up to 40%.",
            ),
        ),
        (
            "income_adequacy_ratio",
            lambda v: v < 0.85,
            AttritionRecommendation(
                priority="HIGH",
                category="compensation",
                action="Conduct salary benchmarking and consider a compensation adjustment.",
                expected_impact="Competitive compensation is a top retention factor for high performers.",
            ),
        ),
        (
            "job_satisfaction",
            lambda v: v < 2.5,
            AttritionRecommendation(
                priority="MEDIUM",
                category="management",
                action="Conduct a structured stay interview to understand dissatisfaction root causes.",
                expected_impact="Addressing root causes of dissatisfaction has outsized retention impact.",
            ),
        ),
        (
            "years_with_curr_manager",
            lambda v: v < 0.5,
            AttritionRecommendation(
                priority="MEDIUM",
                category="management",
                action="Facilitate a structured onboarding to new manager. Assign a skip-level mentor.",
                expected_impact="Employees with new managers are 2x more likely to leave within 6 months.",
            ),
        ),
        (
            "team_health_score",
            lambda v: v < 4.0,
            AttritionRecommendation(
                priority="MEDIUM",
                category="management",
                action="Invest in team-building, resolve inter-team conflicts, and assess manager effectiveness.",
                expected_impact="Team health is a leading indicator of collective attrition.",
            ),
        ),
        (
            "training_hours",
            lambda v: v < 10.0,
            AttritionRecommendation(
                priority="LOW",
                category="career",
                action="Enroll employee in relevant skill-building programs or provide L&D budget.",
                expected_impact="Learning opportunities improve retention especially for younger employees.",
            ),
        ),
        (
            "missed_deadlines",
            lambda v: v > 5,
            AttritionRecommendation(
                priority="MEDIUM",
                category="management",
                action="Investigate root cause of missed deadlines — may indicate overload, disengagement, or unclear priorities.",
                expected_impact="Addressing performance issues early prevents disengagement spiral.",
            ),
        ),
    ]

    def generate(
        self, features_dict: Dict[str, Any], top_n: int = 5
    ) -> List[AttritionRecommendation]:
        """Generate prioritized recommendations based on employee feature values."""
        recommendations = []

        for feature, condition_fn, recommendation in self.RECOMMENDATION_RULES:
            value = features_dict.get(feature)
            if value is not None:
                try:
                    if condition_fn(value):
                        recommendations.append(recommendation)
                except Exception:
                    pass

        # Sort by priority
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 3))

        return recommendations[:top_n]


# Singleton instances
_shap_explainer: Optional[SHAPExplainer] = None
_recommendation_engine = RecommendationEngine()


def get_shap_explainer(registry: ModelRegistry) -> SHAPExplainer:
    global _shap_explainer
    if _shap_explainer is None:
        _shap_explainer = SHAPExplainer(registry)
    return _shap_explainer


def get_recommendation_engine() -> RecommendationEngine:
    return _recommendation_engine
