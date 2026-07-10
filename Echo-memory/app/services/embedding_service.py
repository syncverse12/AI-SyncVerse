"""Wraps Google Gemini embeddings (through LangChain) behind a small,
swappable interface. All credentials come from environment variables."""
from functools import lru_cache
from typing import List

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Generates vector embeddings for memory text using Google Gemini."""

    def __init__(self) -> None:
        self._client = None
        if settings.has_llm_credentials:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings

                self._client = GoogleGenerativeAIEmbeddings(
                    model=settings.GEMINI_EMBEDDING_MODEL,
                    google_api_key=settings.GOOGLE_API_KEY,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Failed to initialize Gemini embeddings client: %s", exc)
                self._client = None
        else:
            logger.warning(
                "GOOGLE_API_KEY not set - EmbeddingService will use a local "
                "deterministic fallback embedding. Set GOOGLE_API_KEY for "
                "production-quality semantic retrieval."
            )

    @property
    def is_using_gemini(self) -> bool:
        return self._client is not None

    def embed_text(self, text: str) -> List[float]:
        if self._client is not None:
            try:
                return self._client.embed_query(text)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Gemini embedding call failed, using fallback: %s", exc)
        return self._fallback_embedding(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if self._client is not None:
            try:
                return self._client.embed_documents(texts)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Gemini batch embedding call failed, using fallback: %s", exc)
        return [self._fallback_embedding(t) for t in texts]

    @staticmethod
    def _fallback_embedding(text: str, dim: int = 384) -> List[float]:
        """Deterministic hash-based embedding used only when no Gemini API
        key is configured, so the system remains runnable (e.g. local dev,
        CI, or health checks) without external credentials. Not suitable for
        production-quality semantic search."""
        import hashlib

        vector = [0.0] * dim
        tokens = text.lower().split()
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(dim):
                vector[i] += digest[i % len(digest)] / 255.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
