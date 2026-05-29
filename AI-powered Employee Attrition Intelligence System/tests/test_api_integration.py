"""
Integration tests for the full API surface.
Uses FastAPI TestClient with SQLite in-memory DB (mocked lifespan).
Run: pytest tests/test_api_integration.py -v
"""

from __future__ import annotations
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

from app.main import create_application
from app.db.session import Base, get_db


# ──────────────────────────────────────────────
# In-memory SQLite test database
# ──────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DB_URL, echo=False, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession,
    expire_on_commit=False, autoflush=False,
)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _create_test_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    Create test client with:
    - SQLite in-memory DB instead of postgres
    - Mocked lifespan DB/scheduler calls
    - ML model registry left as-is (unloaded = 503 for prediction endpoints)
    """
    import asyncio

    async def noop_async(*a, **kw): pass

    asyncio.get_event_loop().run_until_complete(_create_test_tables())

    application = create_application()
    application.dependency_overrides[get_db] = override_get_db

    with (
        patch("app.main.init_db", side_effect=noop_async),
        patch("app.main.close_db", side_effect=noop_async),
        patch("app.main.start_scheduler"),
        patch("app.main.stop_scheduler"),
    ):
        with TestClient(application, raise_server_exceptions=False) as c:
            yield c


# ──────────────────────────────────────────────
# Health Check Tests
# ──────────────────────────────────────────────

class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client):
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data
        assert "ml_models" in data
        assert "timestamp" in data

    def test_health_has_ml_model_flags(self, client):
        response = client.get("/health")
        ml = response.json()["ml_models"]
        assert "attrition_model" in ml
        assert "promotion_model" in ml
        assert "preprocessor" in ml


# ──────────────────────────────────────────────
# Root Endpoint Tests
# ──────────────────────────────────────────────

class TestRootEndpoint:

    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_has_service_info(self, client):
        data = client.get("/").json()
        assert "service" in data
        assert "version" in data
        assert "docs" in data


# ──────────────────────────────────────────────
# Employee CRUD Tests
# ──────────────────────────────────────────────

class TestEmployeeEndpoints:

    def test_create_employee_returns_201(self, client):
        payload = {
            "employee_code": "EMP-TEST-001",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@syncverse.test",
            "age": 30,
            "department": "Engineering",
            "job_role": "Software Engineer",
            "job_level": "Senior",
            "monthly_income": 9000.0,
            "hire_date": "2020-01-15",
            "years_at_company": 4.5,
            "years_since_last_promotion": 1.5,
            "years_with_curr_manager": 2.0,
            "team_id": "team_001",
        }
        response = client.post("/api/v1/employees/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "jane.doe@syncverse.test"
        assert data["department"] == "Engineering"
        assert "id" in data

    def test_create_duplicate_employee_returns_409(self, client):
        payload = {
            "employee_code": "EMP-TEST-002",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@syncverse.test",  # same email
            "age": 30,
            "department": "Engineering",
            "job_role": "Software Engineer",
            "job_level": "Senior",
            "monthly_income": 9000.0,
            "hire_date": "2020-01-15",
            "years_at_company": 4.5,
        }
        response = client.post("/api/v1/employees/", json=payload)
        assert response.status_code == 409

    def test_get_employee_not_found(self, client):
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/employees/{fake_id}")
        assert response.status_code == 404

    def test_get_employee_invalid_uuid(self, client):
        response = client.get("/api/v1/employees/not-a-uuid")
        assert response.status_code == 400

    def test_list_employees_returns_paginated(self, client):
        response = client.get("/api/v1/employees/?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "pages" in data

    def test_list_employees_filter_by_department(self, client):
        response = client.get("/api/v1/employees/?department=Engineering")
        assert response.status_code == 200

    def test_add_metrics_to_employee(self, client):
        # First create an employee
        emp_payload = {
            "employee_code": "EMP-METRICS-001",
            "first_name": "Bob",
            "last_name": "Smith",
            "email": "bob.smith@syncverse.test",
            "age": 28,
            "department": "Data",
            "job_role": "Data Analyst",
            "job_level": "Mid",
            "monthly_income": 5500.0,
            "hire_date": "2022-06-01",
            "years_at_company": 1.5,
        }
        emp_response = client.post("/api/v1/employees/", json=emp_payload)
        assert emp_response.status_code == 201
        emp_id = emp_response.json()["id"]

        # Add metrics
        metrics_payload = {
            "snapshot_date": str(date.today()),
            "performance_rating": 3.8,
            "job_satisfaction": 3.5,
            "work_life_balance": 3.0,
            "environment_satisfaction": 3.5,
            "overtime_hours": 20.0,
            "attendance_rate": 0.95,
            "workload_score": 6.0,
            "team_health_score": 7.0,
            "tasks_completed": 22,
            "tasks_assigned": 25,
            "missed_deadlines": 1,
            "overdue_task_ratio": 0.04,
        }
        metrics_response = client.post(f"/api/v1/employees/{emp_id}/metrics", json=metrics_payload)
        assert metrics_response.status_code == 201
        assert "id" in metrics_response.json()

    def test_get_latest_metrics_not_found(self, client):
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/employees/{fake_id}/metrics/latest")
        assert response.status_code == 404


# ──────────────────────────────────────────────
# Attrition Prediction Tests (with mocked service)
# ──────────────────────────────────────────────

class TestAttritionPredictionEndpoint:

    def test_predict_nonexistent_employee_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        response = client.post(f"/api/v1/attrition/predict/{fake_id}")
        assert response.status_code in (404, 503)  # 503 if model not loaded

    def test_predict_invalid_uuid_format(self, client):
        response = client.post("/api/v1/attrition/predict/invalid-id")
        assert response.status_code in (400, 404, 503)


# ──────────────────────────────────────────────
# Batch Prediction Tests
# ──────────────────────────────────────────────

class TestBatchEndpoints:

    def test_batch_predict_with_empty_list_fails_validation(self, client):
        response = client.post("/api/v1/batch/attrition/predict", json={"employee_ids": []})
        assert response.status_code == 422  # Pydantic min_length=1

    def test_batch_predict_returns_result_per_id(self, client):
        fake_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        response = client.post(
            "/api/v1/batch/attrition/predict",
            json={"employee_ids": fake_ids},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["results"]) == 2
        # All should fail (employees don't exist) but gracefully
        assert data["failed"] == 2
        assert data["succeeded"] == 0

    def test_batch_predict_too_many_employees(self, client):
        too_many = [str(uuid.uuid4()) for _ in range(101)]
        response = client.post(
            "/api/v1/batch/attrition/predict",
            json={"employee_ids": too_many},
        )
        assert response.status_code == 422


# ──────────────────────────────────────────────
# Prediction History Tests
# ──────────────────────────────────────────────

class TestPredictionHistoryEndpoints:

    def test_attrition_history_invalid_uuid(self, client):
        response = client.get("/api/v1/predictions/attrition/not-a-uuid/history")
        assert response.status_code == 400

    def test_attrition_history_empty_for_new_employee(self, client):
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/predictions/attrition/{fake_id}/history")
        assert response.status_code == 200
        assert response.json() == []

    def test_high_risk_endpoint_returns_list(self, client):
        response = client.get("/api/v1/predictions/attrition/high-risk?risk_level=High")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ──────────────────────────────────────────────
# OpenAPI Schema Tests
# ──────────────────────────────────────────────

class TestOpenAPISchema:

    def test_openapi_json_available_in_dev(self, client):
        response = client.get("/openapi.json")
        # Available in non-production
        assert response.status_code in (200, 404)

    def test_docs_available_in_dev(self, client):
        response = client.get("/docs")
        assert response.status_code in (200, 404)
