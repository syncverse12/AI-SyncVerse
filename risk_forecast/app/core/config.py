"""
SyncVerse AI Risk Intelligence Engine
Core configuration — all env-driven, no hardcoded secrets.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ────────────────────────────────────────────────────────────────
    app_name: str = "SyncVerse Risk Intelligence Engine"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # ── API ────────────────────────────────────────────────────────────────
    api_prefix: str = "/api/v1"
    api_secret_key: str = "change-me-in-production"
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Databases ──────────────────────────────────────────────────────────
    postgres_dsn: str = "postgresql+asyncpg://syncverse:syncverse@localhost:5432/risk_engine"
    redis_url: str = "redis://localhost:6379/0"
    redis_pubsub_url: str = "redis://localhost:6379/1"

    # ── Qdrant (Vector DB) ─────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_prefix: str = "syncverse"
    qdrant_vector_size: int = 1536  # OpenAI text-embedding-3-small

    # ── AI Providers ───────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    # Primary provider — "openai" | "gemini"
    ai_provider: Literal["openai", "gemini"] = "openai"

    # ── Celery / Workers ───────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/2"
    celery_result_backend: str = "redis://localhost:6379/3"
    worker_concurrency: int = 4

    # ── Risk Engine ─────────────────────────────────────────────────────────
    # Score weights — configurable without code changes
    risk_weight_deadline: float = 0.25
    risk_weight_workload: float = 0.20
    risk_weight_skill_gap: float = 0.20
    risk_weight_client_alignment: float = 0.10
    risk_weight_inactivity: float = 0.10
    risk_weight_deployment_failure: float = 0.15

    # Alert thresholds
    alert_threshold_low: float = 0.30
    alert_threshold_medium: float = 0.50
    alert_threshold_high: float = 0.70
    alert_threshold_critical: float = 0.85

    # Alert cooldown in seconds (per project per risk category)
    alert_cooldown_seconds: int = 900  # 15 min

    # ── RAG ────────────────────────────────────────────────────────────────
    rag_top_k: int = 5                  # similar historical cases to retrieve
    rag_score_threshold: float = 0.72   # minimum cosine similarity

    # ── Realtime ───────────────────────────────────────────────────────────
    ws_heartbeat_interval: int = 30     # seconds
    live_update_interval: int = 60      # seconds between auto-refreshes

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def qdrant_projects_collection(self) -> str:
        return f"{self.qdrant_collection_prefix}_projects"

    @property
    def qdrant_incidents_collection(self) -> str:
        return f"{self.qdrant_collection_prefix}_incidents"

    @property
    def qdrant_retrospectives_collection(self) -> str:
        return f"{self.qdrant_collection_prefix}_retrospectives"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
