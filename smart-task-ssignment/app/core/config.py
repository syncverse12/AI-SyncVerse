"""
Application settings.
======================
Centralised, environment-driven configuration. Values are read from
process environment variables / Railway Variables, with safe local
defaults so the app also runs unmodified with `docker compose up`.

No local-only assumptions: nothing here hardcodes "localhost" or a
fixed port for the app to bind to.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Server ──────────────────────────────────────────────────────────────
    # Railway injects PORT at runtime; default keeps local/Docker usage simple.
    port: int = 8000
    host: str = "0.0.0.0"
    log_level: str = "INFO"
    environment: str = "development"  # "development" | "production"

    # ── CORS ────────────────────────────────────────────────────────────────
    # Comma-separated origins, e.g. "https://myapp.com,https://staging.myapp.com"
    # "*" is allowed only when cors_allow_credentials is False (browser rule).
    cors_origins: str = "*"
    cors_allow_credentials: bool = False

    # ── Pipeline tuning (previously hardcoded magic numbers) ───────────────
    heartbeat_interval_seconds: int = 30
    max_task_description_length: int = 5000

    @property
    def cors_origin_list(self) -> List[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — reads env vars once per process."""
    return Settings()


settings = get_settings()
