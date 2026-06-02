from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_TEMPERATURE: float = 0.1
    GROQ_MAX_TOKENS: int = 4096

    # Spacy NER toggle — set False to skip if model not installed
    USE_SPACY_NER: bool = True

    # Service metadata
    SERVICE_NAME: str = "Meeting Task Extraction Service"
    SERVICE_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
