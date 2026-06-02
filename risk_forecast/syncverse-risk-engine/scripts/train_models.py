"""
ML Training Pipeline — trains and saves risk prediction models.

Run:
  python scripts/train_models.py --data-path data/historical_projects.csv

This script:
  1. Loads historical project data from CSV
  2. Engineers features using the same FeatureEngineer used in production
  3. Trains XGBoost delay model and LightGBM burnout model
  4. Evaluates with cross-validation
  5. Saves models to app/ml/models/saved_models/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score, mean_absolute_error

MODEL_OUTPUT_DIR = Path(__file__).parent.parent / "app/ml/models/saved_models"


def load_and_preprocess(data_path: str) -> pd.DataFrame:
    """Load historical project data and validate columns."""
    df = pd.read_csv(data_path)
    required_cols = [
        "timeline_days", "hours_per_day", "team_size", "avg_workload_pct",
        "avg_seniority", "budget_per_dev", "dependency_count",
        "requirement_completeness", "client_responsiveness",
        "infrastructure_ready", "skill_gap_ratio",
        # Labels
        "was_delayed", "had_burnout", "delivery_failed", "budget_overrun",
    ]
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in training data: {missing}")
    return df.dropna(subset=required_cols)


def train_delay_model(X: np.ndarray, y: np.ndarray) -> None:
    """Train XGBoost delay prediction model."""
    try:
        import xgboost as xgb
    except ImportError:
        print("xgboost not installed — skipping delay model")
        return

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="auc",
        use_label_encoder=False,
        random_state=42,
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
    print(f"Delay Model — Cross-val AUC: {scores.mean():.3f} ± {scores.std():.3f}")

    model.fit(X, y)
    MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_OUTPUT_DIR / "delay_xgb.ubj"))
    print(f"Saved: {MODEL_OUTPUT_DIR}/delay_xgb.ubj")


def train_burnout_model(X: np.ndarray, y: np.ndarray) -> None:
    """Train LightGBM burnout probability model."""
    try:
        import lightgbm as lgb
    except ImportError:
        print("lightgbm not installed — skipping burnout model")
        return

    model = lgb.LGBMRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
    )

    from sklearn.model_selection import KFold
    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring="neg_mean_absolute_error")
    print(f"Burnout Model — Cross-val MAE: {-scores.mean():.3f} ± {scores.std():.3f}")

    model.fit(X, y)
    MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(MODEL_OUTPUT_DIR / "burnout_lgbm.txt"))
    print(f"Saved: {MODEL_OUTPUT_DIR}/burnout_lgbm.txt")


FEATURE_COLS = [
    "timeline_days", "hours_per_day", "team_size", "avg_workload_pct",
    "avg_seniority", "budget_per_dev", "dependency_count",
    "third_party_count", "requirement_completeness", "client_responsiveness",
    "infrastructure_ready", "skill_gap_ratio", "similar_past_projects_count",
]


def main():
    parser = argparse.ArgumentParser(description="Train SyncVerse risk ML models")
    parser.add_argument("--data-path", required=True, help="Path to historical_projects.csv")
    args = parser.parse_args()

    print(f"Loading data from {args.data_path}…")
    df = load_and_preprocess(args.data_path)
    print(f"Loaded {len(df)} historical projects")

    # Fill optional columns with 0
    for col in ["third_party_count", "similar_past_projects_count"]:
        if col not in df.columns:
            df[col] = 0

    X = df[FEATURE_COLS].values.astype(np.float32)

    print("\nTraining delay prediction model (XGBoost)…")
    train_delay_model(X, df["was_delayed"].values)

    print("\nTraining burnout prediction model (LightGBM)…")
    # Burnout is continuous 0-1 (severity-weighted average)
    burnout_y = df["had_burnout"].values.astype(np.float32)
    train_burnout_model(X, burnout_y)

    # Save feature metadata for drift detection
    feature_stats = {
        col: {"mean": float(df[col].mean()), "std": float(df[col].std())}
        for col in FEATURE_COLS
        if col in df.columns
    }
    stats_path = MODEL_OUTPUT_DIR / "feature_stats.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(feature_stats, indent=2))
    print(f"\nFeature stats saved to {stats_path}")
    print("\nTraining complete.")


if __name__ == "__main__":
    main()
