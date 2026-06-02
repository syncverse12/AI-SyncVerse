"""
Async Groq LLM client — stateless, no external service dependencies.
"""
import json
import re
import logging
from typing import Any, Optional
from groq import AsyncGroq
from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncGroq] = None


def get_groq_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _client


async def chat_complete(
    prompt: str,
    system: str = "You are a helpful AI assistant.",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    expect_json: bool = True,
) -> str:
    client = get_groq_client()
    temp = temperature if temperature is not None else settings.GROQ_TEMPERATURE
    tokens = max_tokens or settings.GROQ_MAX_TOKENS

    kwargs: dict[str, Any] = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temp,
        "max_tokens": tokens,
    }
    if expect_json:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raise


def safe_parse_json(raw: str) -> Optional[dict]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    logger.warning("Could not parse LLM response as JSON")
    return None
