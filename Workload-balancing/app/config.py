"""
config.py
---------
Single source of truth for every tunable value in the service.
Nothing here is hardcoded elsewhere — thresholds, weights, retry counts,
timeouts, and provider selection all flow from environment variables
(with sane defaults) via Pydantic Settings.
"""

from __future__ import annotations
from functools import lru_cache
from typing import Dict, List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ------------------------------------------------------------------
    # App mode
    # ------------------------------------------------------------------
    APP_MODE: Literal["demo", "production"] = Field(default="demo")
    LOG_LEVEL: str = Field(default="INFO")
    PORT: int = Field(default=7860)

    # ------------------------------------------------------------------
    # Backend REST API (Production mode only — never a DB connection)
    # ------------------------------------------------------------------
    BACKEND_API_BASE_URL: Optional[str] = Field(default=None)
    BACKEND_API_TIMEOUT_SECONDS: float = Field(default=10.0)
    BACKEND_API_RETRY_ATTEMPTS: int = Field(default=3)
    BACKEND_API_RETRY_MIN_WAIT: float = Field(default=1.0)
    BACKEND_API_RETRY_MAX_WAIT: float = Field(default=8.0)
    BACKEND_API_KEY: Optional[str] = Field(default=None)
    # Fallback source used only if the primary Tasks endpoint returns nothing
    # for a scope (see docs/DATABASE_ANALYSIS.md §5)
    BACKEND_ENABLE_TASK_EMPLOYEES_FALLBACK: bool = Field(default=True)

    # ------------------------------------------------------------------
    # LLM providers — Groq (primary) -> Gemini (fallback) -> HF (optional)
    # ------------------------------------------------------------------
    LLM_PROVIDER_ORDER: List[str] = Field(default=["groq", "gemini", "huggingface"])

    GROQ_API_KEY: Optional[str] = Field(default=None)
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile")
    GROQ_TIMEOUT_SECONDS: float = Field(default=20.0)

    GEMINI_API_KEY: Optional[str] = Field(default=None)
    GEMINI_MODEL: str = Field(default="gemini-2.0-flash")
    GEMINI_TIMEOUT_SECONDS: float = Field(default=20.0)

    HUGGINGFACE_API_KEY: Optional[str] = Field(default=None)
    HUGGINGFACE_MODEL: str = Field(default="meta-llama/Llama-3.3-70B-Instruct")
    HUGGINGFACE_TIMEOUT_SECONDS: float = Field(default=25.0)

    LLM_RETRY_ATTEMPTS: int = Field(default=2)
    LLM_RETRY_MIN_WAIT: float = Field(default=1.0)
    LLM_RETRY_MAX_WAIT: float = Field(default=6.0)

    # ------------------------------------------------------------------
    # Workload thresholds / weights (mirrors the original balancing module,
    # now externalised instead of hardcoded)
    # ------------------------------------------------------------------
    COMPLEXITY_WEIGHTS: Dict[str, float] = Field(
        default={"low": 0.5, "medium": 1.0, "high": 1.8, "critical": 3.0}
    )
    OVERLOAD_SCORE_THRESHOLD: float = Field(default=60.0)
    UNDERUTILIZED_SCORE_THRESHOLD: float = Field(default=10.0)
    BOTTLENECK_DELAYED_RATIO: float = Field(default=0.4)
    CRITICAL_IMBALANCE_THRESHOLD: int = Field(default=3)
    MIN_AVAILABILITY_TO_RECEIVE: float = Field(default=40.0)
    MAX_RECOMMENDED_ACTIONS: int = Field(default=10)

    # Capacity model (used to turn TimeLogs into Capacity Utilization)
    STANDARD_CAPACITY_HOURS_PER_DAY: float = Field(default=8.0)
    CAPACITY_LOOKBACK_DAYS: int = Field(default=14)

    # ------------------------------------------------------------------
    # Optional internal persistence (SQLite) — snapshots/history only,
    # NEVER mandatory. Demo mode never touches this.
    # ------------------------------------------------------------------
    ENABLE_SNAPSHOT_PERSISTENCE: bool = Field(default=False)
    SQLITE_PATH: str = Field(default="./data/workload_snapshots.db")

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    CORS_ALLOW_ORIGINS: List[str] = Field(default=["*"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
