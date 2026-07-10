"""
Central application settings.

Backend connection settings come from environment variables (.env).
Risk rule weights come from config/risk_rules.yaml so they can change
without touching code, per architectural decision in Phase 2.
"""

from functools import lru_cache
from pathlib import Path
from typing import Dict
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RISK_RULES_PATH = PROJECT_ROOT / "config" / "risk_rules.yaml"


class Settings(BaseSettings):
    backend_base_url: str = "http://localhost:8000"
    backend_request_timeout_seconds: float = 5.0

    llm_provider_order: str = "gemini,groq"  # comma-separated, first = primary
    gemini_api_key: str = ""
    groq_api_key: str = ""
    huggingface_api_key: str = ""

    persistence_backend: str = "sqlite"  # sqlite | postgres | redis (interface-swappable)
    sqlite_path: str = "./risk_microservice.db"

    analysis_version: str = "1.0"
    log_level: str = "INFO"
    demo_mode: bool = False

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_risk_weights() -> Dict[str, float]:
    """
    Loads config/risk_rules.yaml. Falls back to equal weights if the file
    is missing or malformed, rather than crashing the whole service.
    """
    default_weights = {
        "timeline": 0.30,
        "resource": 0.25,
        "productivity": 0.20,
        "communication": 0.10,
        "budget": 0.15,
    }
    if not RISK_RULES_PATH.exists():
        return default_weights

    try:
        with open(RISK_RULES_PATH, "r") as f:
            raw = yaml.safe_load(f) or {}
        weights = {k: float(v.get("weight", 0.0)) for k, v in raw.items() if isinstance(v, dict)}
        return weights or default_weights
    except Exception:
        return default_weights
