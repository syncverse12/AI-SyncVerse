"""
ML Predictor — modular, swappable ML models for risk prediction.

Models:
  - delay_model:       XGBoost classifier (delay probability)
  - burnout_model:     LightGBM regressor (burnout risk 0-1)
  - delivery_model:    XGBoost classifier (delivery failure probability)
  - budget_model:      LightGBM regressor (budget overrun probability)

Architecture:
  - Feature engineering is decoupled from model inference
  - Models are loaded lazily from disk (production) or return stubs (dev)
  - Modular: swap any model by replacing its loader
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import LiveProjectMetrics, ProjectRequirements

logger = get_logger(__name__)

MODEL_DIR = Path(__file__).parent / "saved_models"


class FeatureEngineer:
    """
    Converts domain objects into ML feature vectors.
    Feature names are fixed — models are trained against these exact features.
    """

    PRE_PROJECT_FEATURES = [
        "timeline_days",
        "hours_per_day",
        "team_size",
        "avg_workload_pct",
        "avg_seniority",
        "budget_per_dev",
        "dependency_count",
        "third_party_count",
        "requirement_completeness",
        "client_responsiveness",
        "infrastructure_ready",
        "skill_gap_ratio",
        "similar_past_projects_count",
    ]

    LIVE_FEATURES = [
        "velocity_ratio",
        "overdue_ratio",
        "blocked_ratio",
        "github_activity",
        "pr_bottleneck",
        "deployment_failure_rate",
        "qa_failure_rate",
        "overtime_hours",
        "absence_count",
        "sentiment_score",
        "client_alignment",
        "reassignment_rate",
    ]

    def extract_pre_project(self, req: ProjectRequirements) -> np.ndarray:
        from datetime import timezone
        start = req.start_date
        deadline = req.deadline
        timeline_days = max((deadline - start).days, 1)
        hours_per_day = req.estimated_hours / timeline_days
        team_size = len(req.team)
        avg_workload = sum(m.current_workload_pct for m in req.team) / max(team_size, 1)
        avg_seniority = sum(m.seniority_years for m in req.team) / max(team_size, 1)
        budget_per_dev = req.budget_usd / max(team_size, 1)
        team_skills = {s.lower() for m in req.team for s in m.skills}
        missing = sum(1 for s in req.required_skills if s.lower() not in team_skills)
        skill_gap_ratio = missing / max(len(req.required_skills), 1)

        return np.array([
            timeline_days,
            hours_per_day,
            team_size,
            avg_workload / 100,
            avg_seniority,
            budget_per_dev,
            req.dependencies_count,
            req.third_party_integrations_count,
            req.requirement_completeness_pct / 100,
            req.client_responsiveness / 10,
            float(req.infrastructure_ready),
            skill_gap_ratio,
            len(req.similar_past_projects),
        ], dtype=np.float32).reshape(1, -1)

    def extract_live(self, metrics: LiveProjectMetrics) -> np.ndarray:
        velocity_ratio = metrics.sprint_velocity / max(metrics.planned_velocity, 0.01)
        overdue_ratio = metrics.overdue_tasks / max(metrics.total_tasks, 1)
        blocked_ratio = metrics.blocked_tasks / max(metrics.total_tasks, 1)
        github_activity = min(metrics.github_commits_last_7d / 20, 1.0)
        pr_bottleneck = min(metrics.pr_avg_review_hours / 72, 1.0)
        deployment_rate = min(metrics.deployment_failures_last_30d / 10, 1.0)

        return np.array([
            velocity_ratio,
            overdue_ratio,
            blocked_ratio,
            github_activity,
            pr_bottleneck,
            deployment_rate,
            metrics.qa_failure_rate,
            min(metrics.team_overtime_hours_avg / 40, 1.0),
            min(metrics.team_absences_count / 5, 1.0),
            metrics.negative_sentiment_score,
            metrics.client_alignment_score / 10,
            min(metrics.task_reassignment_count / 10, 1.0),
        ], dtype=np.float32).reshape(1, -1)


class ModelLoader:
    """Lazy model loader — tries to load from disk, falls back to stub."""

    def __init__(self, model_name: str) -> None:
        self._name = model_name
        self._model: Any | None = None

    def load(self) -> Any | None:
        if self._model is not None:
            return self._model

        model_path = MODEL_DIR / f"{self._name}.ubj"  # XGBoost binary
        lgbm_path = MODEL_DIR / f"{self._name}.txt"   # LightGBM text

        if model_path.exists():
            try:
                import xgboost as xgb
                self._model = xgb.Booster()
                self._model.load_model(str(model_path))
                logger.info(f"Loaded XGBoost model: {self._name}")
                return self._model
            except ImportError:
                logger.warning("xgboost not installed, using stub")

        if lgbm_path.exists():
            try:
                import lightgbm as lgb
                self._model = lgb.Booster(model_file=str(lgbm_path))
                logger.info(f"Loaded LightGBM model: {self._name}")
                return self._model
            except ImportError:
                logger.warning("lightgbm not installed, using stub")

        logger.warning(f"Model not found: {self._name} — using rule-based fallback")
        return None


class MLPredictor:
    """
    Wraps all ML models behind a clean async interface.
    Returns adjustments that the scoring engine applies on top of rules.
    """

    def __init__(self) -> None:
        self._fe = FeatureEngineer()
        self._delay_loader = ModelLoader("delay_xgb")
        self._burnout_loader = ModelLoader("burnout_lgbm")
        self._delivery_loader = ModelLoader("delivery_xgb")
        self._budget_loader = ModelLoader("budget_lgbm")

    async def predict_pre_project(self, req: ProjectRequirements) -> dict[str, Any]:
        """
        Run pre-project ML predictions.
        Returns a dict with an 'adjustment' float (0–0.3) and model metadata.
        """
        features = self._fe.extract_pre_project(req)
        model = self._delay_loader.load()

        if model is not None:
            try:
                import xgboost as xgb
                dmatrix = xgb.DMatrix(features)
                delay_prob = float(model.predict(dmatrix)[0])
            except Exception as exc:
                logger.warning("ML prediction failed", error=str(exc))
                delay_prob = self._heuristic_delay(req)
        else:
            delay_prob = self._heuristic_delay(req)

        # ML adjustment = how much the model thinks rules underestimate risk
        rule_timeline = features[0, 1] / 8  # hours_per_day normalized
        adjustment = max(0.0, delay_prob - rule_timeline) * 0.3

        return {
            "delay_probability": round(delay_prob, 4),
            "adjustment": round(adjustment, 4),
            "model_version": "1.0.0",
            "model_used": "xgboost" if model else "heuristic",
        }

    async def predict_live(self, metrics: LiveProjectMetrics) -> dict[str, Any]:
        """Run live metrics through ML models."""
        features = self._fe.extract_live(metrics)
        velocity_ratio = float(features[0, 0])

        # Without trained model: derive adjustment from velocity ratio
        adjustment = max(0.0, (1 - velocity_ratio) * 0.2)

        return {
            "delay_probability": round(1 - velocity_ratio, 4),
            "adjustment": round(adjustment, 4),
            "model_version": "1.0.0",
            "model_used": "heuristic",
        }

    # ── Heuristics (pre-model fallbacks) ────────────────────────────────────

    def _heuristic_delay(self, req: ProjectRequirements) -> float:
        """Simple heuristic delay probability when no trained model is available."""
        score = 0.0
        timeline_days = max((req.deadline - req.start_date).days, 1)
        hours_per_day = req.estimated_hours / timeline_days
        if hours_per_day > 8:
            score += 0.3
        if req.requirement_completeness_pct < 80:
            score += 0.2
        if len(req.team) < 2:
            score += 0.15
        return min(score, 1.0)
