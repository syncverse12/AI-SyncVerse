"""
Real-time translation pipeline.
Translates incoming transcript segments to both Arabic and English in parallel.
"""
import asyncio
import logging
from typing import Optional
from AI_services.app.utils.llm_client import chat_complete, safe_parse_json
from AI_services.app.prompts.templates import TRANSLATION_PROMPT
from AI_services.app.database.redis_client import append_to_list

logger = logging.getLogger(__name__)


class TranslationPipeline:
    """
    Translates text segments between Arabic and English.
    Buffers short segments to reduce API calls.
    """

    def __init__(self, meeting_id: str, source_language: str = "auto"):
        self.meeting_id = meeting_id
        self.source_language = source_language
        self._buffer_en: list[str] = []
        self._buffer_ar: list[str] = []

    async def translate(self, text: str, target_language: str) -> str:
        if not text.strip():
            return ""
        lang_name = "Arabic" if target_language == "ar" else "English"
        prompt = TRANSLATION_PROMPT.format(
            target_language=lang_name,
            text=text,
        )
        try:
            result = await chat_complete(
                prompt=prompt,
                system="You are a professional Arabic-English translator. Output only the translation.",
                temperature=0.1,
                max_tokens=1024,
                expect_json=False,
            )
            return result.strip()
        except Exception as e:
            logger.error(f"Translation error ({target_language}): {e}")
            return text

    async def process_segment(self, text: str, source_lang: str = "en") -> dict:
        """
        Translate a single segment to both languages in parallel.
        Returns dict with both translations.
        """
        tasks = []
        if source_lang == "en":
            tasks = [
                asyncio.create_task(asyncio.coroutine(lambda: text)()),
                asyncio.create_task(self.translate(text, "ar")),
            ]
            results = await asyncio.gather(tasks[1])
            translation_ar = results[0]
            translation_en = text
        else:
            translation_en = await self.translate(text, "en")
            translation_ar = text

        segment = {
            "original": text,
            "en": translation_en,
            "ar": translation_ar,
            "source_lang": source_lang,
        }

        await append_to_list(
            f"transcript:{self.meeting_id}:translations",
            segment,
            ttl=86400,
        )

        return segment

    async def translate_full_transcript(self, full_text_en: str) -> str:
        """Translate a complete English transcript to Arabic."""
        if not full_text_en.strip():
            return ""

        chunks = self._split_into_chunks(full_text_en, max_chars=2000)
        translated_chunks = []
        for chunk in chunks:
            ar = await self.translate(chunk, "ar")
            translated_chunks.append(ar)

        return "\n".join(translated_chunks)

    @staticmethod
    def _split_into_chunks(text: str, max_chars: int = 2000) -> list[str]:
        sentences = text.replace(". ", ".|").split("|")
        chunks, current = [], ""
        for sentence in sentences:
            if len(current) + len(sentence) > max_chars and current:
                chunks.append(current.strip())
                current = sentence
            else:
                current += " " + sentence
        if current.strip():
            chunks.append(current.strip())
        return chunks


async def detect_language(text: str) -> str:
    """Detect if text is primarily Arabic or English."""
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    ratio = arabic_chars / max(len(text), 1)
    return "ar" if ratio > 0.3 else "en"
