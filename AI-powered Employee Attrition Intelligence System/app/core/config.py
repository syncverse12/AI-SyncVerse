"""
Core configuration module using Pydantic Settings.
Loads from environment variables and .env file.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "SyncVerse Attrition Intelligence"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production-must-be-32-chars-min"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Database
    database_url: str = "postgresql+asyncpg://syncverse:syncverse_pass@localhost:5432/syncverse_attrition"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600

    # ML Models
    model_path: str = "./ml_models"
    attrition_model_file: str = "attrition_model.joblib"
    promotion_model_file: str = "promotion_model.joblib"
    preprocessor_file: str = "preprocessor.joblib"
    feature_names_file: str = "feature_names.json"

    # Scheduler
    prediction_recalc_interval_hours: int = 24
    enable_background_jobs: bool = True

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"

    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:8080"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def attrition_model_path(self) -> str:
        return f"{self.model_path}/{self.attrition_model_file}"

    @property
    def promotion_model_path(self) -> str:
        return f"{self.model_path}/{self.promotion_model_file}"

    @property
    def preprocessor_path(self) -> str:
        return f"{self.model_path}/{self.preprocessor_file}"

    @property
    def feature_names_path(self) -> str:
        return f"{self.model_path}/{self.feature_names_file}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
