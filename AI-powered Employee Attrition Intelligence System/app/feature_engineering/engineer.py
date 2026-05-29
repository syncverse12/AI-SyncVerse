"""
Feature Engineering Module.
Transforms raw employee data into ML-ready features.
Generates derived features capturing burnout, stability, and attrition signals.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import numpy as np
from loguru import logger


@dataclass
class RawEmployeeData:
    """Raw data collected from DB for a single employee."""
    # Core employee info
    employee_id: str
    age: int
    department: str
    job_role: str
    job_level: str
    monthly_income: float
    years_at_company: float
    years_since_last_promotion: float
    years_with_curr_manager: float
    years_in_current_role: float = 0.0

    # Survey scores (1-5)
    performance_rating: float = 3.0
    job_satisfaction: float = 3.0
    work_life_balance: float = 3.0
    environment_satisfaction: float = 3.0
    relationship_satisfaction: float = 3.0

    # Work patterns
    overtime_hours: float = 0.0
    standard_hours: float = 160.0
    attendance_rate: float = 1.0

    # Workload
    workload_score: float = 5.0
    team_health_score: float = 7.0
    collaboration_score: float = 7.0

    # Task metrics
    tasks_completed: int = 0
    tasks_assigned: int = 1
    missed_deadlines: int = 0
    overdue_task_ratio: float = 0.0

    # Leadership & promotion
    leadership_score: float = 5.0
    promotion_velocity: float = 3.0  # avg years between promos
    training_hours: float = 0.0

    # Label (for training only)
    attrition: Optional[int] = None
    promotion: Optional[int] = None


@dataclass
class EngineeredFeatures:
    """ML-ready feature vector after engineering."""

    # Original features
    age: float
    monthly_income: float
    years_at_company: float
    years_since_last_promotion: float
    years_with_curr_manager: float
    years_in_current_role: float
    performance_rating: float
    job_satisfaction: float
    work_life_balance: float
    environment_satisfaction: float
    relationship_satisfaction: float
    overtime_hours: float
    attendance_rate: float
    workload_score: float
    team_health_score: float
    collaboration_score: float
    tasks_completed: float
    missed_deadlines: float
    overdue_task_ratio: float
    leadership_score: float
    promotion_velocity: float
    training_hours: float

    # Categorical (encoded later)
    department: str
    job_role: str
    job_level: str

    # ── Derived Features ──
    overtime_ratio: float              # overtime / standard hours
    deadline_failure_rate: float       # missed / assigned tasks
    promotion_gap_years: float         # years since last promotion normalized
    workload_pressure_score: float     # composite pressure signal
    stability_score: float             # tenure & manager stability composite
    burnout_signal: float              # composite burnout indicator
    satisfaction_composite: float      # avg of all satisfaction scores
    performance_trend: float           # perf relative to workload
    career_stagnation_score: float     # low promo velocity + high tenure
    income_adequacy_ratio: float       # income vs role-expected (normalized)
    task_efficiency_score: float       # completed / assigned with quality weight
    engagement_score: float            # composite engagement metric

    # Labels (optional, only in training)
    attrition: Optional[int] = None
    promotion: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)

    def to_numeric_dict(self) -> Dict[str, float]:
        """Return only numeric features, excluding categoricals and labels."""
        exclude = {"department", "job_role", "job_level", "attrition", "promotion"}
        return {k: v for k, v in self.to_dict().items() if k not in exclude}


class FeatureEngineer:
    """
    Transforms RawEmployeeData into EngineeredFeatures.
    All transformations are deterministic and invertible where possible.
    """

    # Job level → numeric mapping
    JOB_LEVEL_MAP = {
        "Junior": 1, "Mid": 2, "Senior": 3,
        "Lead": 4, "Manager": 5, "Director": 6,
        "VP": 7, "C-Level": 8,
    }

    # Expected income ranges by level (rough normalization baseline)
    INCOME_BASELINE = {
        1: 3000, 2: 5000, 3: 8000, 4: 10000,
        5: 13000, 6: 18000, 7: 25000, 8: 35000,
    }

    def engineer(self, raw: RawEmployeeData) -> EngineeredFeatures:
        """Main entry point: engineer all features from raw data."""
        try:
            overtime_ratio = self._overtime_ratio(raw)
            deadline_failure_rate = self._deadline_failure_rate(raw)
            promotion_gap = self._promotion_gap(raw)
            workload_pressure = self._workload_pressure(raw, overtime_ratio)
            stability = self._stability_score(raw)
            burnout = self._burnout_signal(raw, overtime_ratio, workload_pressure)
            satisfaction = self._satisfaction_composite(raw)
            perf_trend = self._performance_trend(raw, workload_pressure)
            stagnation = self._career_stagnation(raw)
            income_ratio = self._income_adequacy(raw)
            task_efficiency = self._task_efficiency(raw)
            engagement = self._engagement_score(raw, satisfaction, perf_trend)

            return EngineeredFeatures(
                # Raw numeric
                age=float(raw.age),
                monthly_income=raw.monthly_income,
                years_at_company=raw.years_at_company,
                years_since_last_promotion=raw.years_since_last_promotion,
                years_with_curr_manager=raw.years_with_curr_manager,
                years_in_current_role=raw.years_in_current_role,
                performance_rating=raw.performance_rating,
                job_satisfaction=raw.job_satisfaction,
                work_life_balance=raw.work_life_balance,
                environment_satisfaction=raw.environment_satisfaction,
                relationship_satisfaction=raw.relationship_satisfaction,
                overtime_hours=raw.overtime_hours,
                attendance_rate=raw.attendance_rate,
                workload_score=raw.workload_score,
                team_health_score=raw.team_health_score,
                collaboration_score=raw.collaboration_score,
                tasks_completed=float(raw.tasks_completed),
                missed_deadlines=float(raw.missed_deadlines),
                overdue_task_ratio=raw.overdue_task_ratio,
                leadership_score=raw.leadership_score,
                promotion_velocity=raw.promotion_velocity,
                training_hours=raw.training_hours,
                # Categorical
                department=raw.department,
                job_role=raw.job_role,
                job_level=raw.job_level,
                # Derived
                overtime_ratio=overtime_ratio,
                deadline_failure_rate=deadline_failure_rate,
                promotion_gap_years=promotion_gap,
                workload_pressure_score=workload_pressure,
                stability_score=stability,
                burnout_signal=burnout,
                satisfaction_composite=satisfaction,
                performance_trend=perf_trend,
                career_stagnation_score=stagnation,
                income_adequacy_ratio=income_ratio,
                task_efficiency_score=task_efficiency,
                engagement_score=engagement,
                # Labels
                attrition=raw.attrition,
                promotion=raw.promotion,
            )
        except Exception as exc:
            logger.error(f"Feature engineering failed for {raw.employee_id}: {exc}")
            raise

    # ──────────────────────────────────────────
    # Derived Feature Calculations
    # ──────────────────────────────────────────

    def _overtime_ratio(self, raw: RawEmployeeData) -> float:
        """Fraction of overtime to standard hours. 0 = no overtime, 1+ = extreme."""
        std = max(raw.standard_hours, 1.0)
        return round(min(raw.overtime_hours / std, 2.0), 4)

    def _deadline_failure_rate(self, raw: RawEmployeeData) -> float:
        """Ratio of missed deadlines to tasks assigned."""
        assigned = max(raw.tasks_assigned, 1)
        return round(min(raw.missed_deadlines / assigned, 1.0), 4)

    def _promotion_gap(self, raw: RawEmployeeData) -> float:
        """
        Normalized promotion gap. 
        Score > 1 means overdue for promotion relative to their velocity.
        """
        velocity = max(raw.promotion_velocity, 0.5)
        return round(raw.years_since_last_promotion / velocity, 4)

    def _workload_pressure(self, raw: RawEmployeeData, overtime_ratio: float) -> float:
        """
        Composite workload pressure score (0-10).
        High workload + high overtime + many tasks = high pressure.
        """
        pressure = (
            raw.workload_score * 0.4
            + overtime_ratio * 10 * 0.35
            + raw.overdue_task_ratio * 10 * 0.25
        )
        return round(min(pressure, 10.0), 4)

    def _stability_score(self, raw: RawEmployeeData) -> float:
        """
        Tenure & relationship stability score (0-10).
        High score = stable long-term employee with stable manager.
        """
        # Normalize years to 0-10, caps at 15 years
        tenure_score = min(raw.years_at_company / 15.0, 1.0) * 10
        manager_score = min(raw.years_with_curr_manager / 10.0, 1.0) * 10
        return round((tenure_score * 0.6 + manager_score * 0.4), 4)

    def _burnout_signal(
        self, raw: RawEmployeeData, overtime_ratio: float, workload_pressure: float
    ) -> float:
        """
        Composite burnout signal (0-10). High = burnout risk.
        Combines low WLB, high overtime, low satisfaction, high workload.
        """
        # Invert satisfaction scores (low satisfaction = high burnout contribution)
        inv_wlb = (5.0 - raw.work_life_balance) / 4.0
        inv_sat = (5.0 - raw.job_satisfaction) / 4.0
        inv_env = (5.0 - raw.environment_satisfaction) / 4.0

        burnout = (
            inv_wlb * 10 * 0.30
            + overtime_ratio * 10 * 0.25
            + workload_pressure * 0.25
            + inv_sat * 10 * 0.10
            + inv_env * 10 * 0.10
        )
        return round(min(burnout, 10.0), 4)

    def _satisfaction_composite(self, raw: RawEmployeeData) -> float:
        """Average of all satisfaction dimensions (1-5)."""
        scores = [
            raw.job_satisfaction,
            raw.work_life_balance,
            raw.environment_satisfaction,
            raw.relationship_satisfaction,
        ]
        return round(np.mean(scores), 4)

    def _performance_trend(self, raw: RawEmployeeData, workload_pressure: float) -> float:
        """
        Performance relative to workload pressure.
        High performer under high pressure = resilient. 
        Low performer under low pressure = disengaged.
        """
        norm_perf = raw.performance_rating / 5.0
        norm_workload = workload_pressure / 10.0
        # Positive = performing above expectations relative to pressure
        return round(norm_perf - norm_workload * 0.5, 4)

    def _career_stagnation(self, raw: RawEmployeeData) -> float:
        """
        Career stagnation score (0-10).
        High = stuck in role without advancement relative to tenure.
        """
        # Long time in current role + long time since promotion = stagnation
        role_stagnation = min(raw.years_in_current_role / 8.0, 1.0) * 10
        promo_stagnation = min(raw.years_since_last_promotion / 5.0, 1.0) * 10
        # High velocity employees expect faster promos
        velocity_factor = min(1.0 / max(raw.promotion_velocity, 0.5), 2.0)
        score = (role_stagnation * 0.4 + promo_stagnation * 0.6) * velocity_factor
        return round(min(score, 10.0), 4)

    def _income_adequacy(self, raw: RawEmployeeData) -> float:
        """
        How well current income matches expected for job level.
        < 1.0 = underpaid, > 1.0 = well paid.
        """
        level_num = self.JOB_LEVEL_MAP.get(raw.job_level, 2)
        baseline = self.INCOME_BASELINE.get(level_num, 5000)
        return round(min(raw.monthly_income / baseline, 3.0), 4)

    def _task_efficiency(self, raw: RawEmployeeData) -> float:
        """Task completion efficiency (0-1)."""
        assigned = max(raw.tasks_assigned, 1)
        completion_rate = min(raw.tasks_completed / assigned, 1.0)
        # Penalize overdue tasks
        penalty = raw.overdue_task_ratio * 0.3
        return round(max(completion_rate - penalty, 0.0), 4)

    def _engagement_score(
        self, raw: RawEmployeeData, satisfaction: float, perf_trend: float
    ) -> float:
        """
        Overall engagement score (0-10).
        High satisfaction + strong performance + collaboration = high engagement.
        """
        sat_norm = (satisfaction - 1) / 4.0  # 0-1
        collab_norm = (raw.collaboration_score - 1) / 9.0  # 0-1
        training_boost = min(raw.training_hours / 40.0, 1.0) * 0.1

        engagement = (
            sat_norm * 10 * 0.40
            + max(perf_trend, 0) * 10 * 0.30
            + collab_norm * 10 * 0.20
            + training_boost * 10 * 0.10
        )
        return round(min(engagement, 10.0), 4)


# Singleton instance
feature_engineer = FeatureEngineer()
