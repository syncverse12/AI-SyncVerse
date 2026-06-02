from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_TEMPERATURE: float = 0.2
    GROQ_MAX_TOKENS: int = 4096

    # Max transcript chars sent to LLM per request
    # Long transcripts are chunked and summaries merged
    MAX_TRANSCRIPT_CHARS: int = 14000

    SERVICE_NAME: str = "Meeting Summary Service"
    SERVICE_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
