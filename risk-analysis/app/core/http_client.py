"""
Single shared httpx.AsyncClient for all calls to the backend.

Centralizing this (rather than constructing a client per call) means one
place to configure timeouts, base_url, and connection pooling — and one
place to point at a mock server during tests.
"""

import httpx
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    backend_base_url: str = "http://localhost:8000"
    backend_request_timeout_seconds: float = 5.0

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def build_http_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.backend_base_url,
        timeout=httpx.Timeout(settings.backend_request_timeout_seconds),
    )
