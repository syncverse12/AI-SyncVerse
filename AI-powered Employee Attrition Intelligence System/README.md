# SyncVerse Attrition Intelligence System

> **Production-ready AI-powered Employee Attrition Intelligence Microservice**
> Predicts attrition risk, recommends promotions, explains decisions — built for SyncVerse.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Training the ML Models](#training-the-ml-models)
- [API Reference](#api-reference)
- [Example Requests & Responses](#example-requests--responses)
- [Feature Engineering](#feature-engineering)
- [Explainability (SHAP)](#explainability-shap)
- [Background Jobs](#background-jobs)
- [Testing](#testing)
- [Docker Deployment](#docker-deployment)
- [Integration Guide](#integration-guide)

---

## Overview

The SyncVerse Attrition Intelligence System is a standalone FastAPI microservice that:

1. **Predicts employee attrition** — XGBoost model calibrated with probability outputs, SHAP explanations, and risk tiers (Low / Medium / High)
2. **Recommends promotions** — Readiness scoring with reasoning, strengths, and development areas
3. **Analyzes team risk** — Aggregated burnout indicators, workload distribution, and team-level recommendations
4. **Explains every prediction** — SHAP values translated into human-readable factor descriptions
5. **Runs scheduled recalculation** — Background jobs keep predictions fresh without manual triggers

---

## Architecture

```
Request → FastAPI Endpoint
             ↓
         Service Layer          (orchestration)
             ↓
     Repository Layer           (DB access via async SQLAlchemy)
             ↓
   Feature Engineering          (derived features from raw data)
             ↓
      ML Inference Pipeline     (XGBoost → calibrated probabilities)
             ↓
    SHAP Explainability Layer   (top factors + human-readable summary)
             ↓
   Recommendation Engine        (rule-based retention actions)
             ↓
    Prediction Repository       (persist to PostgreSQL)
             ↓
        API Response
```

Clean separation: no ML logic in endpoints, no DB queries in services.

---

## Tech Stack

| Layer          | Technology                            |
|----------------|---------------------------------------|
| API Framework  | FastAPI 0.111 + Uvicorn               |
| ML             | XGBoost 2.0 + scikit-learn + SHAP     |
| Database       | PostgreSQL 16 (asyncpg driver)        |
| ORM            | SQLAlchemy 2.0 async                  |
| Validation     | Pydantic v2                           |
| Caching        | Redis 7 (graceful degradation)        |
| Scheduling     | APScheduler 3.10                      |
| Logging        | Loguru                                |
| Containerization | Docker + Docker Compose             |
| Testing        | Pytest + pytest-asyncio               |

---

## Project Structure

```
syncverse-attrition/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── attrition.py          # POST /api/v1/attrition/predict/{id}
│   │       │   ├── promotion_team.py     # POST /api/v1/promotion/predict/{id}
│   │       │   │                         # GET  /api/v1/team-risk/{team_id}
│   │       │   └── health.py             # GET  /health
│   │       └── router.py
│   ├── core/
│   │   ├── config.py                     # Pydantic settings from .env
│   │   ├── exceptions.py                 # Custom exception hierarchy
│   │   └── logging.py                    # Loguru configuration
│   ├── db/
│   │   └── session.py                    # Async SQLAlchemy engine + get_db()
│   ├── models/                           # SQLAlchemy ORM models
│   │   ├── employee.py                   # Employee, enums
│   │   ├── metrics.py                    # EmployeeMetrics, Task, Attendance, Reviews
│   │   └── predictions.py                # AttritionPrediction, PromotionPrediction
│   ├── schemas/
│   │   └── schemas.py                    # Pydantic request/response schemas
│   ├── feature_engineering/
│   │   └── engineer.py                   # 12 derived ML features
│   ├── ml/
│   │   ├── train.py                      # Full training pipeline
│   │   └── predict.py                    # ModelRegistry + inference
│   ├── explainability/
│   │   └── shap_explainer.py             # SHAP + RecommendationEngine
│   ├── services/
│   │   └── attrition_service.py          # AttritionService, PromotionService, TeamRiskService
│   ├── repositories/
│   │   └── employee_repository.py        # EmployeeRepository, PredictionRepository
│   ├── utils/
│   │   └── cache.py                      # Redis cache wrapper
│   ├── workers/
│   │   └── scheduler.py                  # APScheduler background jobs
│   └── main.py                           # FastAPI app factory + lifespan
├── scripts/
│   └── generate_seed_data.py             # Synthetic data generator
├── tests/
│   └── test_attrition_service.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── pytest.ini
```

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local dev)

### 1. Clone and configure

```bash
git clone <repo>
cd syncverse-attrition
cp .env.example .env
# Edit .env with your settings
```

### 2. Start infrastructure

```bash
docker-compose up postgres redis -d
```

### 3. Train the ML models

```bash
# One-time training using synthetic data
docker-compose --profile training run --rm trainer
```

Or locally:

```bash
pip install -r requirements.txt
python scripts/generate_seed_data.py --n 3000 --output data/training_data.csv
python -m app.ml.train --data data/training_data.csv --model-dir ml_models
```

### 4. Seed the database (optional but recommended for testing)

```bash
docker-compose --profile seeding run --rm seeder
```

### 5. Start the API

```bash
docker-compose up api
```

API is now live at **http://localhost:8000**
Swagger UI: **http://localhost:8000/docs**

---

## Configuration

All configuration is via environment variables or `.env` file.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Environment (`development`, `production`) |
| `DATABASE_URL` | (postgres) | PostgreSQL async URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `MODEL_PATH` | `./ml_models` | Directory where trained models are stored |
| `PREDICTION_RECALC_INTERVAL_HOURS` | `24` | How often background jobs recalculate predictions |
| `ENABLE_BACKGROUND_JOBS` | `true` | Toggle scheduled recalculation |
| `SECRET_KEY` | (required) | App secret, minimum 32 chars |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS origins (comma-separated) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Training the ML Models

### Using synthetic data (quick start)

```bash
python -m app.ml.train
# Auto-generates 2000 synthetic employees and trains both models
```

### Using your own data

Your CSV must include all features listed in the Feature Engineering section plus `attrition` (0/1) and `promotion` (0/1) columns.

```bash
python -m app.ml.train --data /path/to/your_data.csv --model-dir ./ml_models
```

**Models trained:**
- `attrition_model.joblib` — Calibrated XGBoost for attrition probability
- `promotion_model.joblib` — XGBoost for promotion readiness
- `preprocessor.joblib` — sklearn ColumnTransformer (scaling + encoding)
- `attrition_model_raw.joblib` — Raw XGBoost for SHAP explanations
- `feature_names.json` — Feature metadata

Training output includes ROC-AUC, Average Precision, and full classification reports.

---

## API Reference

### POST `/api/v1/attrition/predict/{employee_id}`

Predict attrition risk for a single employee.

**Path params:**
- `employee_id` — UUID of the employee

**Response:** `AttritionPredictionResponse`

---

### POST `/api/v1/promotion/predict/{employee_id}`

Assess promotion readiness for a single employee.

**Path params:**
- `employee_id` — UUID of the employee

**Response:** `PromotionResponse`

---

### GET `/api/v1/team-risk/{team_id}`

Analyze attrition risk across an entire team.

**Path params:**
- `team_id` — Team identifier string (e.g., `team_001`)

**Response:** `TeamRiskResponse`

---

### GET `/health`

Service health check including DB, Redis, and ML model status.

---

## Example Requests & Responses

### Attrition Prediction

```bash
curl -X POST http://localhost:8000/api/v1/attrition/predict/550e8400-e29b-41d4-a716-446655440000
```

```json
{
  "employee_id": "550e8400-e29b-41d4-a716-446655440000",
  "employee_name": "Sarah Mitchell",
  "attrition_probability": 0.8247,
  "risk_level": "High",
  "top_risk_factors": [
    {
      "feature": "burnout_signal",
      "display_name": "Burnout Signal",
      "impact": 0.3821,
      "direction": "positive_risk",
      "description": "Burnout Signal significantly increases attrition risk."
    },
    {
      "feature": "work_life_balance",
      "display_name": "Work-Life Balance",
      "impact": 0.2743,
      "direction": "positive_risk",
      "description": "Work-Life Balance significantly increases attrition risk."
    },
    {
      "feature": "career_stagnation_score",
      "display_name": "Career Stagnation",
      "impact": 0.2105,
      "direction": "positive_risk",
      "description": "Career Stagnation significantly increases attrition risk."
    },
    {
      "feature": "income_adequacy_ratio",
      "display_name": "Income Adequacy",
      "impact": -0.1450,
      "direction": "negative_risk",
      "description": "Income Adequacy slightly decreases attrition risk."
    }
  ],
  "recommendations": [
    {
      "priority": "HIGH",
      "category": "wellbeing",
      "action": "Initiate immediate wellbeing check-in and consider temporary workload reduction.",
      "expected_impact": "Can reduce burnout-related attrition risk by 20-35%."
    },
    {
      "priority": "HIGH",
      "category": "career",
      "action": "Schedule a career development conversation. Explore promotion or lateral growth paths.",
      "expected_impact": "Career clarity reduces stagnation-driven attrition by up to 40%."
    },
    {
      "priority": "HIGH",
      "category": "workload",
      "action": "Review and redistribute workload. Enforce overtime limits. Consider additional hiring.",
      "expected_impact": "Reducing excessive overtime is one of the strongest retention levers."
    }
  ],
  "explanation_summary": "This employee shows high attrition risk (82% probability). Key risk drivers include: Burnout Signal, Work-Life Balance, Career Stagnation. Protective factors: Income Adequacy.",
  "model_version": "1.0.0",
  "predicted_at": "2024-11-15T09:30:00Z"
}
```

---

### Promotion Recommendation

```bash
curl -X POST http://localhost:8000/api/v1/promotion/predict/550e8400-e29b-41d4-a716-446655440001
```

```json
{
  "employee_id": "550e8400-e29b-41d4-a716-446655440001",
  "employee_name": "David Park",
  "promotion_readiness_score": 83.4,
  "promotion_recommended": true,
  "recommended_role": "Lead",
  "promotion_reasoning": [
    "Strong performance rating above threshold.",
    "High leadership potential score.",
    "Exceptional employee engagement.",
    "Sufficient tenure for next level.",
    "Active investment in professional development."
  ],
  "top_strengths": [
    "High performance rating",
    "Strong collaboration skills",
    "Excellent task efficiency",
    "Active self-development commitment"
  ],
  "development_areas": [],
  "predicted_at": "2024-11-15T09:30:00Z"
}
```

---

### Team Risk Analysis

```bash
curl http://localhost:8000/api/v1/team-risk/team_007
```

```json
{
  "team_id": "team_007",
  "total_employees": 12,
  "average_attrition_probability": 0.5831,
  "high_risk_count": 5,
  "medium_risk_count": 4,
  "low_risk_count": 3,
  "burnout_indicator": "High",
  "average_workload_score": 7.8,
  "average_team_health": 5.2,
  "average_work_life_balance": 2.4,
  "top_risk_employees": [
    {
      "employee_id": "550e8400-e29b-41d4-a716-446655440000",
      "employee_name": "Sarah Mitchell",
      "job_role": "Software Engineer",
      "attrition_probability": 0.8247,
      "risk_level": "High"
    },
    {
      "employee_id": "660e9400-f39c-51e5-b827-557766551111",
      "employee_name": "Carlos Vega",
      "job_role": "DevOps Engineer",
      "attrition_probability": 0.7612,
      "risk_level": "High"
    }
  ],
  "workload_distribution": {
    "low": 1,
    "medium": 3,
    "high": 5,
    "overloaded": 3
  },
  "team_recommendations": [
    "URGENT: 5 high-risk employees detected. Schedule immediate 1:1 retention conversations with manager.",
    "Team workload is critically high. Review task distribution and consider headcount additions.",
    "Work-life balance scores are alarming. Implement flexible working policies immediately."
  ],
  "analysis_date": "2024-11-15T09:30:00Z"
}
```

---

### Health Check

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "database": "healthy",
  "redis": "healthy",
  "ml_models": {
    "attrition_model": true,
    "promotion_model": true,
    "preprocessor": true
  },
  "timestamp": "2024-11-15T09:30:00Z"
}
```

---

## Feature Engineering

The `FeatureEngineer` class produces 12 derived features from raw employee data:

| Derived Feature | Formula / Logic | Attrition Signal |
|---|---|---|
| `overtime_ratio` | `overtime_hours / standard_hours` | High → risk ↑ |
| `deadline_failure_rate` | `missed / tasks_assigned` | High → risk ↑ |
| `promotion_gap_years` | `years_since_promo / promo_velocity` | >1.0 → risk ↑ |
| `workload_pressure_score` | Composite: workload + overtime + overdue | High → risk ↑ |
| `stability_score` | Tenure + manager stability composite | High → risk ↓ |
| `burnout_signal` | Low WLB + high overtime + workload pressure | High → risk ↑↑ |
| `satisfaction_composite` | Mean of 4 satisfaction dimensions | Low → risk ↑ |
| `performance_trend` | Performance relative to workload | Low → risk ↑ |
| `career_stagnation_score` | Role tenure + promo gap normalized | High → risk ↑↑ |
| `income_adequacy_ratio` | Income vs job-level baseline | <0.85 → risk ↑ |
| `task_efficiency_score` | Completion rate minus overdue penalty | Low → risk ↑ |
| `engagement_score` | Satisfaction + performance + collaboration | Low → risk ↑ |

---

## Explainability (SHAP)

Each attrition prediction includes SHAP-based explanations:

- **Impact value** — Magnitude of each feature's contribution to the predicted probability
- **Direction** — `positive_risk` (increases risk) or `negative_risk` (decreases risk)
- **Human-readable description** — Auto-generated sentence per factor
- **Narrative summary** — One-paragraph explanation of the overall prediction

SHAP TreeExplainer runs on the raw (uncalibrated) XGBoost model for consistent Shapley values.

---

## Background Jobs

The APScheduler runs a periodic job to recalculate predictions for all active employees:

```
Every N hours (configurable via PREDICTION_RECALC_INTERVAL_HOURS):
  → Fetch all active employees
  → Run full prediction pipeline for each
  → Update is_latest flags in DB
  → Log summary statistics
```

Enable/disable via `ENABLE_BACKGROUND_JOBS=true/false`.

---

## Testing

```bash
# Install test deps
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=app --cov-report=term-missing
```

Test coverage includes:
- Feature engineering bounds and correctness
- Derived feature correlations (burnout, engagement)
- Recommendation engine rules
- Pydantic schema validation

---

## Docker Deployment

### Full stack

```bash
docker-compose up -d
```

### One-time model training

```bash
docker-compose --profile training run --rm trainer
```

### One-time database seed

```bash
docker-compose --profile seeding run --rm seeder
```

### Services

| Service | Port | Description |
|---|---|---|
| `api` | 8000 | FastAPI application |
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis cache |

### Volumes

| Volume | Contents |
|---|---|
| `postgres_data` | Persistent database storage |
| `redis_data` | Redis AOF persistence |
| `ml_models` | Trained model artifacts |
| `app_logs` | Application logs |

---

## Integration Guide

### Calling from your existing SyncVerse backend

```python
import httpx

BASE_URL = "http://syncverse-attrition:8000"

async def get_attrition_risk(employee_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/attrition/predict/{employee_id}",
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

async def get_team_dashboard(team_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/team-risk/{team_id}",
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
```

### Interpreting risk levels

| Risk Level | Probability | Recommended Action |
|---|---|---|
| **Low** | < 35% | Routine monitoring |
| **Medium** | 35–65% | Proactive check-in within 30 days |
| **High** | ≥ 65% | Immediate manager intervention |

---

## License

MIT © SyncVerse
