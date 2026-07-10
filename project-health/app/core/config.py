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

    # ── Gemini ───────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_llm_model: str = "gemini-2.5-flash"

    # ── Scoring weights ──────────────────────────────────────────────────────
    health_weight_goal_progress: float = 0.40
    health_weight_completion_rate: float = 0.25
    health_weight_efficiency: float = 0.20
    health_weight_delay: float = 0.15

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
