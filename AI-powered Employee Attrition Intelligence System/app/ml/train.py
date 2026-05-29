"""
ML Training Pipeline for Attrition & Promotion models.
Run this script to train and persist models:
    python -m app.ml.train
"""

from __future__ import annotations
import os
import json
import warnings
from pathlib import Path
from typing import Tuple, Dict, Any

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OrdinalEncoder
from sklearn.metrics import (
    classification_report, roc_auc_score,
    confusion_matrix, average_precision_score,
)
from sklearn.calibration import CalibratedClassifierCV
from imblearn.over_sampling import SMOTE
import xgboost as xgb
from loguru import logger

warnings.filterwarnings("ignore")


CATEGORICAL_FEATURES = ["department", "job_role", "job_level"]

NUMERIC_FEATURES = [
    "age", "monthly_income", "years_at_company", "years_since_last_promotion",
    "years_with_curr_manager", "years_in_current_role", "performance_rating",
    "job_satisfaction", "work_life_balance", "environment_satisfaction",
    "relationship_satisfaction", "overtime_hours", "attendance_rate",
    "workload_score", "team_health_score", "collaboration_score",
    "tasks_completed", "missed_deadlines", "overdue_task_ratio",
    "leadership_score", "promotion_velocity", "training_hours",
    "overtime_ratio", "deadline_failure_rate", "promotion_gap_years",
    "workload_pressure_score", "stability_score", "burnout_signal",
    "satisfaction_composite", "performance_trend", "career_stagnation_score",
    "income_adequacy_ratio", "task_efficiency_score", "engagement_score",
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def build_preprocessor() -> ColumnTransformer:
    """Build sklearn ColumnTransformer for preprocessing."""
    numeric_transformer = Pipeline([
        ("scaler", StandardScaler()),
    ])
    categorical_transformer = Pipeline([
        ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
    ])
    return ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERIC_FEATURES),
            ("cat", categorical_transformer, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )


def build_attrition_model() -> xgb.XGBClassifier:
    """XGBoost classifier for attrition prediction."""
    return xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )


def build_promotion_model() -> xgb.XGBClassifier:
    """XGBoost classifier for promotion recommendation."""
    return xgb.XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.9,
        min_child_weight=3,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )


def evaluate_model(
    model, X_test: np.ndarray, y_test: np.ndarray, label: str
) -> Dict[str, Any]:
    """Compute evaluation metrics."""
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    roc_auc = roc_auc_score(y_test, y_prob)
    avg_prec = average_precision_score(y_test, y_prob)
    report = classification_report(y_test, y_pred, output_dict=True)

    metrics = {
        "roc_auc": round(roc_auc, 4),
        "avg_precision": round(avg_prec, 4),
        "classification_report": report,
    }

    logger.info(
        f"\n{'='*50}\n{label} Evaluation\n"
        f"ROC-AUC: {roc_auc:.4f} | Avg Precision: {avg_prec:.4f}\n"
        f"{classification_report(y_test, y_pred)}"
    )
    return metrics


def train_attrition_model(
    df: pd.DataFrame, model_dir: str
) -> Tuple[Pipeline, Dict[str, Any]]:
    """Train and persist attrition prediction model."""
    logger.info("Training attrition model...")

    X = df[ALL_FEATURES].copy()
    y = df["attrition"].copy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    preprocessor = build_preprocessor()
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)

    # Handle class imbalance with SMOTE
    smote = SMOTE(random_state=42, k_neighbors=5)
    X_train_res, y_train_res = smote.fit_resample(X_train_proc, y_train)
    logger.info(
        f"SMOTE resampling: {dict(zip(*np.unique(y_train_res, return_counts=True)))}"
    )

    # Train model
    clf = build_attrition_model()
    clf.fit(X_train_res, y_train_res)

    # Calibrate probabilities
    calibrated = CalibratedClassifierCV(clf, method="isotonic", cv="prefit")
    calibrated.fit(X_train_proc, y_train)

    # Evaluate
    metrics = evaluate_model(calibrated, X_test_proc, y_test, "Attrition")

    # Persist
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(preprocessor, f"{model_dir}/preprocessor.joblib")
    joblib.dump(calibrated, f"{model_dir}/attrition_model.joblib")

    # Save feature names
    with open(f"{model_dir}/feature_names.json", "w") as f:
        json.dump({"numeric": NUMERIC_FEATURES, "categorical": CATEGORICAL_FEATURES}, f, indent=2)

    # Save raw XGB for SHAP
    joblib.dump(clf, f"{model_dir}/attrition_model_raw.joblib")

    logger.info(f"Attrition model saved to {model_dir}")
    return calibrated, metrics


def train_promotion_model(
    df: pd.DataFrame, model_dir: str
) -> Tuple[Pipeline, Dict[str, Any]]:
    """Train and persist promotion recommendation model."""
    logger.info("Training promotion model...")

    X = df[ALL_FEATURES].copy()
    y = df["promotion"].copy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    preprocessor = build_preprocessor()
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)

    clf = build_promotion_model()
    clf.fit(X_train_proc, y_train)

    metrics = evaluate_model(clf, X_test_proc, y_test, "Promotion")

    joblib.dump(clf, f"{model_dir}/promotion_model.joblib")
    logger.info(f"Promotion model saved to {model_dir}")
    return clf, metrics


def run_training(data_path: str = None, model_dir: str = "./ml_models") -> None:
    """Full training pipeline entry point."""
    if data_path and os.path.exists(data_path):
        logger.info(f"Loading training data from {data_path}")
        df = pd.read_csv(data_path)
    else:
        logger.warning("No data path provided. Generating synthetic training data...")
        from scripts.generate_seed_data import generate_training_dataframe
        df = generate_training_dataframe(n_employees=2000)

    logger.info(f"Dataset shape: {df.shape}")
    logger.info(f"Attrition rate: {df['attrition'].mean():.2%}")
    logger.info(f"Promotion rate: {df['promotion'].mean():.2%}")

    attrition_model, attrition_metrics = train_attrition_model(df, model_dir)
    promotion_model, promotion_metrics = train_promotion_model(df, model_dir)

    # Save training summary
    summary = {
        "attrition_model": attrition_metrics,
        "promotion_model": promotion_metrics,
        "dataset": {
            "n_records": len(df),
            "attrition_rate": float(df["attrition"].mean()),
            "promotion_rate": float(df["promotion"].mean()),
        },
    }
    with open(f"{model_dir}/training_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info("Training pipeline complete. Models saved.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train SyncVerse Attrition Models")
    parser.add_argument("--data", type=str, default=None, help="Path to training CSV")
    parser.add_argument("--model-dir", type=str, default="./ml_models", help="Model output directory")
    args = parser.parse_args()

    run_training(data_path=args.data, model_dir=args.model_dir)
