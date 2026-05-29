"""
Attrition Service.
Orchestrates data collection → feature engineering → prediction → explanation → storage.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import InsufficientDataException, PredictionFailedException
from app.repositories.employee_repository import EmployeeRepository, PredictionRepository
from app.feature_engineering.engineer import feature_engineer, RawEmployeeData
from app.ml.predict import AttritionPredictor, PromotionPredictor, model_registry
from app.explainability.shap_explainer import (
    get_shap_explainer, get_recommendation_engine
)
from app.models.predictions import AttritionPrediction, PromotionPrediction
from app.schemas.schemas import AttritionPredictionResponse, PromotionResponse


class AttritionService:
    """
    Orchestrates the full attrition prediction pipeline:
    1. Fetch employee data from DB
    2. Engineer features
    3. Run ML prediction
    4. Generate SHAP explanations
    5. Generate recommendations
    6. Persist results
    7. Return structured response
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.employee_repo = EmployeeRepository(db)
        self.prediction_repo = PredictionRepository(db)
        self.attrition_predictor = AttritionPredictor(model_registry)
        self.shap_explainer = get_shap_explainer(model_registry)
        self.recommendation_engine = get_recommendation_engine()

    async def predict_attrition(
        self, employee_id: str, trigger: str = "manual"
    ) -> AttritionPredictionResponse:
        """
        Full attrition prediction pipeline for a single employee.
        """
        logger.info(f"Starting attrition prediction for employee: {employee_id}")

        # 1. Fetch data
        employee = await self.employee_repo.get_by_id(employee_id)
        metrics = await self.employee_repo.get_latest_metrics(employee.id)

        if metrics is None:
            raise InsufficientDataException(
                employee_id, ["employee_metrics (no snapshot found)"]
            )

        # 2. Build raw data
        raw = self._build_raw_data(employee, metrics)

        # 3. Engineer features
        try:
            features = feature_engineer.engineer(raw)
        except Exception as exc:
            raise PredictionFailedException(f"Feature engineering error: {exc}")

        # 4. Predict
        try:
            probability, risk_level, X_proc = self.attrition_predictor.predict(features)
        except Exception as exc:
            raise PredictionFailedException(f"Model inference error: {exc}")

        # 5. SHAP Explanations
        risk_factors = self.shap_explainer.explain(X_proc, top_n=6)
        explanation_summary = self.shap_explainer.generate_summary(risk_factors, probability)

        # 6. Recommendations
        recommendations = self.recommendation_engine.generate(
            features.to_dict(), top_n=5
        )

        # 7. Persist
        prediction_record = AttritionPrediction(
            employee_id=employee.id,
            attrition_probability=probability,
            risk_level=risk_level,
            top_risk_factors=[rf.model_dump() for rf in risk_factors],
            recommendations=[rec.model_dump() for rec in recommendations],
            model_version=settings.app_version,
            trigger=trigger,
            is_latest=True,
        )
        await self.prediction_repo.save_attrition_prediction(prediction_record)

        # 8. Build response
        now = datetime.now(timezone.utc)
        return AttritionPredictionResponse(
            employee_id=str(employee.id),
            employee_name=f"{employee.first_name} {employee.last_name}",
            attrition_probability=round(probability, 4),
            risk_level=risk_level,
            top_risk_factors=risk_factors,
            recommendations=recommendations,
            explanation_summary=explanation_summary,
            model_version=settings.app_version,
            predicted_at=now,
        )

    def _build_raw_data(self, employee, metrics) -> RawEmployeeData:
        """Map ORM objects to RawEmployeeData dataclass."""
        return RawEmployeeData(
            employee_id=str(employee.id),
            age=employee.age,
            department=employee.department,
            job_role=employee.job_role,
            job_level=employee.job_level,
            monthly_income=employee.monthly_income,
            years_at_company=employee.years_at_company,
            years_since_last_promotion=employee.years_since_last_promotion or 0.0,
            years_with_curr_manager=employee.years_with_curr_manager or 0.0,
            years_in_current_role=employee.years_in_current_role or 0.0,
            # Metrics
            performance_rating=metrics.performance_rating,
            job_satisfaction=metrics.job_satisfaction,
            work_life_balance=metrics.work_life_balance,
            environment_satisfaction=metrics.environment_satisfaction,
            relationship_satisfaction=metrics.relationship_satisfaction or 3.0,
            overtime_hours=metrics.overtime_hours,
            standard_hours=metrics.standard_hours,
            attendance_rate=metrics.attendance_rate,
            workload_score=metrics.workload_score,
            team_health_score=metrics.team_health_score,
            collaboration_score=metrics.collaboration_score or 7.0,
            tasks_completed=metrics.tasks_completed,
            tasks_assigned=max(metrics.tasks_assigned, 1),
            missed_deadlines=metrics.missed_deadlines,
            overdue_task_ratio=metrics.overdue_task_ratio,
            leadership_score=metrics.leadership_score or 5.0,
            promotion_velocity=metrics.promotion_velocity or 3.0,
            training_hours=metrics.training_hours or 0.0,
        )


class PromotionService:
    """
    Orchestrates the promotion recommendation pipeline.
    """

    PROMOTION_REASONING_RULES = [
        ("performance_rating", lambda v: v >= 4.0, "Strong performance rating above threshold."),
        ("leadership_score", lambda v: v >= 7.0, "High leadership potential score."),
        ("engagement_score", lambda v: v >= 7.0, "Exceptional employee engagement."),
        ("years_at_company", lambda v: v >= 2.0, "Sufficient tenure for next level."),
        ("task_efficiency_score", lambda v: v >= 0.8, "High task completion efficiency."),
        ("collaboration_score", lambda v: v >= 7.0, "Strong collaboration and teamwork."),
        ("training_hours", lambda v: v >= 30.0, "Active investment in professional development."),
        ("career_stagnation_score", lambda v: v >= 7.0, "Overdue for promotion based on trajectory."),
    ]

    def __init__(self, db: AsyncSession):
        self.db = db
        self.employee_repo = EmployeeRepository(db)
        self.prediction_repo = PredictionRepository(db)
        self.promotion_predictor = PromotionPredictor(model_registry)

    async def predict_promotion(self, employee_id: str) -> PromotionResponse:
        """Full promotion recommendation pipeline."""
        logger.info(f"Starting promotion prediction for employee: {employee_id}")

        employee = await self.employee_repo.get_by_id(employee_id)
        metrics = await self.employee_repo.get_latest_metrics(employee.id)

        if metrics is None:
            raise InsufficientDataException(employee_id, ["employee_metrics"])

        raw = self._build_raw_data(employee, metrics)
        features = feature_engineer.engineer(raw)

        score, recommended, recommended_role = self.promotion_predictor.predict(features)
        features_dict = features.to_dict()

        reasoning = self._build_reasoning(features_dict, recommended)
        strengths = self._identify_strengths(features_dict)
        dev_areas = self._identify_dev_areas(features_dict)

        # Persist
        record = PromotionPrediction(
            employee_id=employee.id,
            promotion_readiness_score=score,
            promotion_recommended=recommended,
            recommended_role=recommended_role,
            promotion_reasoning=reasoning,
            top_strengths=strengths,
            development_areas=dev_areas,
            model_version=settings.app_version,
            is_latest=True,
        )
        await self.prediction_repo.save_promotion_prediction(record)

        return PromotionResponse(
            employee_id=str(employee.id),
            employee_name=f"{employee.first_name} {employee.last_name}",
            promotion_readiness_score=score,
            promotion_recommended=recommended,
            recommended_role=recommended_role,
            promotion_reasoning=reasoning,
            top_strengths=strengths,
            development_areas=dev_areas,
            predicted_at=datetime.now(timezone.utc),
        )

    def _build_raw_data(self, employee, metrics) -> RawEmployeeData:
        return RawEmployeeData(
            employee_id=str(employee.id),
            age=employee.age,
            department=employee.department,
            job_role=employee.job_role,
            job_level=employee.job_level,
            monthly_income=employee.monthly_income,
            years_at_company=employee.years_at_company,
            years_since_last_promotion=employee.years_since_last_promotion or 0.0,
            years_with_curr_manager=employee.years_with_curr_manager or 0.0,
            years_in_current_role=employee.years_in_current_role or 0.0,
            performance_rating=metrics.performance_rating,
            job_satisfaction=metrics.job_satisfaction,
            work_life_balance=metrics.work_life_balance,
            environment_satisfaction=metrics.environment_satisfaction,
            relationship_satisfaction=metrics.relationship_satisfaction or 3.0,
            overtime_hours=metrics.overtime_hours,
            attendance_rate=metrics.attendance_rate,
            workload_score=metrics.workload_score,
            team_health_score=metrics.team_health_score,
            collaboration_score=metrics.collaboration_score or 7.0,
            tasks_completed=metrics.tasks_completed,
            tasks_assigned=max(metrics.tasks_assigned, 1),
            missed_deadlines=metrics.missed_deadlines,
            overdue_task_ratio=metrics.overdue_task_ratio,
            leadership_score=metrics.leadership_score or 5.0,
            promotion_velocity=metrics.promotion_velocity or 3.0,
            training_hours=metrics.training_hours or 0.0,
        )

    def _build_reasoning(self, features: dict, recommended: bool) -> list[str]:
        reasons = []
        for feat, condition, msg in self.PROMOTION_REASONING_RULES:
            val = features.get(feat)
            if val is not None:
                try:
                    if condition(val):
                        reasons.append(msg)
                except Exception:
                    pass
        if not reasons:
            reasons = [
                "Further development needed before next promotion."
                if not recommended
                else "Ready for next level based on combined performance indicators."
            ]
        return reasons[:5]

    def _identify_strengths(self, features: dict) -> list[str]:
        strengths = []
        checks = [
            ("performance_rating", lambda v: v >= 4.0, "High performance rating"),
            ("collaboration_score", lambda v: v >= 7.5, "Strong collaboration skills"),
            ("task_efficiency_score", lambda v: v >= 0.85, "Excellent task efficiency"),
            ("leadership_score", lambda v: v >= 7.5, "Strong leadership qualities"),
            ("attendance_rate", lambda v: v >= 0.95, "Outstanding attendance and reliability"),
            ("training_hours", lambda v: v >= 40.0, "Active self-development commitment"),
            ("engagement_score", lambda v: v >= 7.5, "Highly engaged employee"),
        ]
        for feat, cond, label in checks:
            val = features.get(feat)
            if val is not None and cond(val):
                strengths.append(label)
        return strengths[:4]

    def _identify_dev_areas(self, features: dict) -> list[str]:
        areas = []
        checks = [
            ("leadership_score", lambda v: v < 5.0, "Leadership skill development"),
            ("collaboration_score", lambda v: v < 5.0, "Cross-team collaboration"),
            ("training_hours", lambda v: v < 10.0, "Professional development investment"),
            ("overdue_task_ratio", lambda v: v > 0.2, "Task delivery consistency"),
            ("performance_rating", lambda v: v < 3.0, "Performance improvement"),
            ("missed_deadlines", lambda v: v > 3, "Deadline management"),
        ]
        for feat, cond, label in checks:
            val = features.get(feat)
            if val is not None and cond(val):
                areas.append(label)
        return areas[:3]


class TeamRiskService:
    """Aggregates attrition predictions at the team level."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.employee_repo = EmployeeRepository(db)
        self.attrition_service = AttritionService(db)

    async def analyze_team(self, team_id: str):
        """Compute team-level risk summary."""
        from app.schemas.schemas import (
            TeamRiskResponse, TeamMemberRisk, WorkloadDistribution
        )
        from datetime import datetime, timezone
        import statistics

        employees = await self.employee_repo.get_by_team(team_id)
        if not employees:
            from app.core.exceptions import TeamNotFoundException
            raise TeamNotFoundException(team_id)

        member_risks = []
        probabilities = []
        workload_scores = []
        health_scores = []
        wlb_scores = []

        for emp in employees:
            try:
                result = await self.attrition_service.predict_attrition(
                    str(emp.id), trigger="team_analysis"
                )
                member_risks.append(
                    TeamMemberRisk(
                        employee_id=str(emp.id),
                        employee_name=f"{emp.first_name} {emp.last_name}",
                        job_role=emp.job_role,
                        attrition_probability=result.attrition_probability,
                        risk_level=result.risk_level,
                    )
                )
                probabilities.append(result.attrition_probability)

                metrics = await self.employee_repo.get_latest_metrics(emp.id)
                if metrics:
                    workload_scores.append(metrics.workload_score)
                    health_scores.append(metrics.team_health_score)
                    wlb_scores.append(metrics.work_life_balance)
            except Exception as exc:
                logger.warning(f"Skipping employee {emp.id} in team analysis: {exc}")

        if not probabilities:
            probabilities = [0.0]

        avg_prob = statistics.mean(probabilities)
        high_risk = sum(1 for p in probabilities if p >= 0.65)
        medium_risk = sum(1 for p in probabilities if 0.35 <= p < 0.65)
        low_risk = sum(1 for p in probabilities if p < 0.35)
        avg_workload = statistics.mean(workload_scores) if workload_scores else 5.0
        avg_health = statistics.mean(health_scores) if health_scores else 7.0
        avg_wlb = statistics.mean(wlb_scores) if wlb_scores else 3.0

        burnout = self._assess_burnout(avg_prob, avg_workload, avg_wlb)
        team_recs = self._team_recommendations(avg_prob, high_risk, avg_workload, avg_wlb)

        # Workload distribution
        wld = WorkloadDistribution(
            low=sum(1 for s in workload_scores if s < 4),
            medium=sum(1 for s in workload_scores if 4 <= s < 7),
            high=sum(1 for s in workload_scores if 7 <= s < 9),
            overloaded=sum(1 for s in workload_scores if s >= 9),
        )

        member_risks.sort(key=lambda m: m.attrition_probability, reverse=True)

        return TeamRiskResponse(
            team_id=team_id,
            total_employees=len(employees),
            average_attrition_probability=round(avg_prob, 4),
            high_risk_count=high_risk,
            medium_risk_count=medium_risk,
            low_risk_count=low_risk,
            burnout_indicator=burnout,
            average_workload_score=round(avg_workload, 2),
            average_team_health=round(avg_health, 2),
            average_work_life_balance=round(avg_wlb, 2),
            top_risk_employees=member_risks[:5],
            workload_distribution=wld,
            team_recommendations=team_recs,
            analysis_date=datetime.now(timezone.utc),
        )

    @staticmethod
    def _assess_burnout(avg_prob: float, avg_workload: float, avg_wlb: float) -> str:
        score = avg_prob * 40 + (avg_workload / 10) * 30 + ((5 - avg_wlb) / 4) * 30
        if score >= 70:
            return "Critical"
        elif score >= 50:
            return "High"
        elif score >= 30:
            return "Moderate"
        return "Low"

    @staticmethod
    def _team_recommendations(
        avg_prob: float, high_risk_count: int, avg_workload: float, avg_wlb: float
    ) -> list[str]:
        recs = []
        if high_risk_count >= 3:
            recs.append(
                f"URGENT: {high_risk_count} high-risk employees detected. "
                "Schedule immediate 1:1 retention conversations with manager."
            )
        if avg_workload >= 7.5:
            recs.append("Team workload is critically high. Review task distribution and consider headcount additions.")
        if avg_wlb < 2.5:
            recs.append("Work-life balance scores are alarming. Implement flexible working policies immediately.")
        if avg_prob >= 0.5:
            recs.append("Team attrition risk is elevated. Consider a team health workshop and manager coaching.")
        if not recs:
            recs.append("Team health is stable. Continue monitoring monthly and invest in team development.")
        return recs
