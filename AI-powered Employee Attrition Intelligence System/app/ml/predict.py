"""
ML Inference Pipeline.
Loads trained models and performs predictions for attrition & promotion.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import numpy as np
import pandas as pd
import joblib
from loguru import logger

from app.core.config import settings
from app.core.exceptions import ModelNotLoadedException
from app.feature_engineering.engineer import EngineeredFeatures
from app.ml.train import ALL_FEATURES, NUMERIC_FEATURES, CATEGORICAL_FEATURES


class ModelRegistry:
    """
    Singleton registry for ML models.
    Loads models once on startup and provides thread-safe access.
    """

    _instance: Optional["ModelRegistry"] = None

    def __init__(self):
        self.attrition_model = None
        self.attrition_model_raw = None  # raw XGB for SHAP
        self.promotion_model = None
        self.preprocessor = None
        self.feature_names: Dict[str, list] = {}
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_models(self) -> None:
        """Load all models from disk. Called once on app startup."""
        model_dir = settings.model_path
        os.makedirs(model_dir, exist_ok=True)

        try:
            attrition_path = settings.attrition_model_path
            preprocessor_path = settings.preprocessor_path
            promotion_path = settings.promotion_model_path
            feature_names_path = settings.feature_names_path
            raw_attrition_path = f"{model_dir}/attrition_model_raw.joblib"

            if not os.path.exists(attrition_path):
                logger.warning(
                    f"Attrition model not found at {attrition_path}. "
                    "Run training pipeline first: python -m app.ml.train"
                )
                return

            self.preprocessor = joblib.load(preprocessor_path)
            self.attrition_model = joblib.load(attrition_path)
            self.promotion_model = joblib.load(promotion_path)

            if os.path.exists(raw_attrition_path):
                self.attrition_model_raw = joblib.load(raw_attrition_path)

            if os.path.exists(feature_names_path):
                with open(feature_names_path) as f:
                    self.feature_names = json.load(f)

            self._loaded = True
            logger.info("ML models loaded successfully.")

        except Exception as exc:
            logger.error(f"Failed to load ML models: {exc}")
            self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def ensure_loaded(self, model_name: str) -> None:
        if not self._loaded:
            raise ModelNotLoadedException(model_name)


class AttritionPredictor:
    """Inference for attrition prediction."""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def predict(
        self, features: EngineeredFeatures
    ) -> Tuple[float, str, np.ndarray]:
        """
        Returns:
            (probability, risk_level, preprocessed_feature_array)
        """
        self.registry.ensure_loaded("attrition_model")

        df = self._to_dataframe(features)
        X_proc = self.registry.preprocessor.transform(df)

        probability = float(
            self.registry.attrition_model.predict_proba(X_proc)[0][1]
        )
        risk_level = self._classify_risk(probability)

        return probability, risk_level, X_proc

    def _to_dataframe(self, features: EngineeredFeatures) -> pd.DataFrame:
        data = features.to_dict()
        # Keep only training features, in order
        row = {f: data.get(f, 0.0) for f in ALL_FEATURES}
        return pd.DataFrame([row])

    @staticmethod
    def _classify_risk(prob: float) -> str:
        if prob >= 0.65:
            return "High"
        elif prob >= 0.35:
            return "Medium"
        return "Low"


class PromotionPredictor:
    """Inference for promotion recommendation."""

    LEVEL_PROGRESSION = {
        "Junior": "Mid",
        "Mid": "Senior",
        "Senior": "Lead",
        "Lead": "Manager",
        "Manager": "Director",
        "Director": "VP",
        "VP": "C-Level",
        "C-Level": "C-Level",
    }

    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def predict(
        self, features: EngineeredFeatures
    ) -> Tuple[float, bool, Optional[str]]:
        """
        Returns:
            (readiness_score 0-100, recommended bool, recommended_role)
        """
        self.registry.ensure_loaded("promotion_model")

        df = self._to_dataframe(features)
        X_proc = self.registry.preprocessor.transform(df)

        proba = float(
            self.registry.promotion_model.predict_proba(X_proc)[0][1]
        )
        readiness_score = round(proba * 100, 2)
        recommended = readiness_score >= 60.0

        recommended_role = None
        if recommended:
            recommended_role = self.LEVEL_PROGRESSION.get(features.job_level)

        return readiness_score, recommended, recommended_role

    def _to_dataframe(self, features: EngineeredFeatures) -> pd.DataFrame:
        data = features.to_dict()
        row = {f: data.get(f, 0.0) for f in ALL_FEATURES}
        return pd.DataFrame([row])


# Singleton accessor
model_registry = ModelRegistry.get_instance()
