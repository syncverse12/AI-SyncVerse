import json
import re
from typing import Any, Optional
from groq import AsyncGroq
from AI_services.app.config import settings

_client: Optional[AsyncGroq] = None


def get_groq_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _client


async def chat_complete(
    prompt: str,
    system: str = "You are a helpful AI assistant.",
    temperature: float = None,
    max_tokens: int = 4096,
    expect_json: bool = True,
) -> str:
    client = get_groq_client()
    temp = temperature if temperature is not None else settings.GROQ_TEMPERATURE

    kwargs: dict[str, Any] = {
        "model": settings.GROQ_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
    }
    if expect_json:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def safe_parse_json(raw: str) -> Optional[dict]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None
