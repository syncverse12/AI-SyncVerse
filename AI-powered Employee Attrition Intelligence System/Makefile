# ─────────────────────────────────────────────
# SyncVerse Attrition Intelligence — Makefile
# ─────────────────────────────────────────────

.PHONY: help install dev train seed test lint format docker-up docker-down docker-build docker-logs clean

# Default target
help:
	@echo ""
	@echo "SyncVerse Attrition Intelligence System"
	@echo "======================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install Python dependencies"
	@echo "  make setup          Full local setup (install + dirs)"
	@echo ""
	@echo "Development:"
	@echo "  make dev            Start dev server with auto-reload"
	@echo "  make train          Train ML models (uses synthetic data)"
	@echo "  make train DATA=path/to/data.csv  Train with your own data"
	@echo "  make seed           Generate synthetic training CSV"
	@echo "  make seed-db        Seed the database with test employees"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-api       Run API integration tests only"
	@echo "  make coverage       Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run ruff linter"
	@echo "  make format         Auto-format with ruff"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-up      Start all services"
	@echo "  make docker-down    Stop all services"
	@echo "  make docker-train   Train models inside Docker"
	@echo "  make docker-seed    Seed DB inside Docker"
	@echo "  make docker-logs    Tail API logs"
	@echo ""
	@echo "  make clean          Remove generated files"
	@echo ""

# ──────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────

install:
	pip install --upgrade pip
	pip install -r requirements.txt

setup: install
	cp -n .env.example .env || true
	mkdir -p ml_models logs data
	@echo "Setup complete. Edit .env then run: make train && make dev"

# ──────────────────────────────────────────────
# Development
# ──────────────────────────────────────────────

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info

train:
ifdef DATA
	python -m app.ml.train --data $(DATA) --model-dir ./ml_models
else
	python -m app.ml.train --model-dir ./ml_models
endif

seed:
	python scripts/generate_seed_data.py --n 3000 --output ./data/training_data.csv

seed-db:
	python scripts/generate_seed_data.py --seed-db --n 200

migrate:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "$(MSG)"

# ──────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────

test:
	pytest tests/ -v

test-unit:
	pytest tests/test_attrition_service.py -v

test-api:
	pytest tests/test_api_integration.py -v

coverage:
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html
	@echo "HTML coverage report: htmlcov/index.html"

# ──────────────────────────────────────────────
# Code Quality
# ──────────────────────────────────────────────

lint:
	ruff check app/ scripts/ tests/

format:
	ruff format app/ scripts/ tests/
	ruff check --fix app/ scripts/ tests/

# ──────────────────────────────────────────────
# Docker
# ──────────────────────────────────────────────

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d postgres redis
	@echo "Waiting for DB to be ready..."
	@sleep 3
	docker-compose up -d api
	@echo ""
	@echo "Services running:"
	@echo "  API:      http://localhost:8000"
	@echo "  Docs:     http://localhost:8000/docs"
	@echo "  Health:   http://localhost:8000/health"

docker-down:
	docker-compose down

docker-train:
	docker-compose --profile training run --rm trainer

docker-seed:
	docker-compose --profile seeding run --rm seeder

docker-logs:
	docker-compose logs -f api

docker-restart:
	docker-compose restart api

docker-ps:
	docker-compose ps

docker-clean:
	docker-compose down -v --remove-orphans

# ──────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	@echo "Cleaned up."
