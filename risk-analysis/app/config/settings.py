"""
Central application settings, loaded once from environment variables / .env.
Every layer that needs configuration imports `get_settings()` from here
instead of reading os.environ directly.
"""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # --- Backend integration ---
    backend_base_url: str = "http://localhost:8000"
    backend_request_timeout_seconds: float = 5.0

    # --- LLM providers ---
    llm_primary_provider: str = "gemini"
    llm_fallback_provider: str = "groq"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    huggingface_api_key: str = ""
    llm_model_name: str = "qwen2.5:7b"
    llm_request_timeout_seconds: float = 20.0
    llm_max_retries: int = 3

    # --- Persistence ---
    persistence_backend: str = "sqlite"  # sqlite | postgres | redis (future)
    sqlite_db_path: str = str(BASE_DIR / "data" / "risk_history.db")

    # --- Risk rules ---
    risk_rules_config_path: str = str(BASE_DIR / "app" / "config" / "risk_rules.yaml")

    # --- App ---
    app_env: str = "development"
    log_level: str = "INFO"
    analysis_version: str = "1.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
