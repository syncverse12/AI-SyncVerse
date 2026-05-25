"""
app/core/config.py
Central configuration loaded from environment / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM / Embeddings ─────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_llm_model: str = "gpt-4o"
    openai_embedding_dimensions: int = 1536

    # ── Qdrant ───────────────────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""
    qdrant_collection_requirements: str = "requirements_vectors"
    qdrant_collection_tasks: str = "tasks_vectors"
    qdrant_collection_deliverables: str = "deliverables_vectors"
    qdrant_collection_notes: str = "notes_vectors"

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    embedding_cache_ttl: int = 86_400

    # ── Scoring weights ──────────────────────────────────────────────────────
    health_weight_goal_progress: float = 0.40
    health_weight_completion_rate: float = 0.25
    health_weight_efficiency: float = 0.20
    health_weight_delay: float = 0.15

    # ── RAG ──────────────────────────────────────────────────────────────────
    rag_top_k: int = 8
    rag_score_threshold: float = 0.55

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
