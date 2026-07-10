"""
Central application configuration.

Every value is sourced from environment variables (or a local .env file during
development). No secret ever appears hardcoded in source code.
"""
import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General ---
    APP_NAME: str = "SyncVerse Echo"
    APP_ENV: str = Field(default="development")  # development | production
    LOG_LEVEL: str = Field(default="INFO")
    API_PREFIX: str = Field(default="/echo")

    # --- CORS ---
    CORS_ORIGINS: str = Field(default="*")

    # --- Database ---
    # If DATABASE_URL is not set, Echo automatically falls back to a local
    # SQLite file (see `effective_database_url` below). This makes the app
    # deployable on Hugging Face Spaces with zero external services - a
    # managed Postgres is still recommended for production, but is no
    # longer required just to get Echo running.
    DATABASE_URL: Optional[str] = Field(default=None)
    SQLITE_PATH: str = Field(default="/data/echo.db")
    DB_POOL_SIZE: int = Field(default=5)
    DB_MAX_OVERFLOW: int = Field(default=10)

    # --- ChromaDB ---
    CHROMA_PERSIST_DIR: str = Field(default="/data/chroma")
    CHROMA_COLLECTION_PREFIX: str = Field(default="syncverse_echo")

    # --- Google Gemini (via environment variables only) ---
    GOOGLE_API_KEY: str = Field(default="")
    GEMINI_CHAT_MODEL: str = Field(default="gemini-2.5-flash")
    GEMINI_EMBEDDING_MODEL: str = Field(default="models/gemini-embedding-001")

    # --- Groq (primary chat provider) ---
    # Gemini remains the embedding provider (unchanged - the RAG/retrieval
    # pipeline is untouched); Groq is only used for chat completions, with
    # Gemini kept as an automatic fallback if Groq is unavailable.
    GROQ_API_KEY: str = Field(default="")
    GROQ_CHAT_MODEL: str = Field(default="llama-3.3-70b-versatile")

    # --- Chat provider selection ---
    # "groq" (default): Groq primary, Gemini automatic fallback.
    # "gemini": Gemini only (legacy / explicit override).
    CHAT_PROVIDER: str = Field(default="groq")

    # Network resilience for the primary chat provider.
    LLM_REQUEST_TIMEOUT_SECONDS: float = Field(default=20.0)
    LLM_MAX_RETRIES: int = Field(default=1)

    # --- Echo behaviour ---
    ECHO_MAX_CONTEXT_MEMORIES: int = Field(default=8)
    ECHO_CONVERSATION_HISTORY_LIMIT: int = Field(default=12)
    ECHO_MIN_CONFIDENCE: float = Field(default=0.35)

    @field_validator("GOOGLE_API_KEY")
    @classmethod
    def _warn_missing_key(cls, v: str) -> str:
        # Intentionally does not raise: allows the app to boot (e.g. for
        # health checks / CI) even before secrets are configured. Callers
        # that need Gemini must check `settings.has_llm_credentials`.
        return v

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.GOOGLE_API_KEY)

    @property
    def has_groq_credentials(self) -> bool:
        return bool(self.GROQ_API_KEY)

    @property
    def chat_provider_normalized(self) -> str:
        return (self.CHAT_PROVIDER or "groq").strip().lower()

    @property
    def using_sqlite_fallback(self) -> bool:
        return not bool(self.DATABASE_URL)

    @property
    def effective_database_url(self) -> str:
        """The actual SQLAlchemy URL to connect with.

        Returns DATABASE_URL as-is when configured (PostgreSQL in
        production). Otherwise falls back to a local SQLite file so the
        app remains fully functional - and trivially deployable - without
        requiring an external database provider.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL

        db_dir = os.path.dirname(self.SQLITE_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        return f"sqlite:///{self.SQLITE_PATH}"

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
