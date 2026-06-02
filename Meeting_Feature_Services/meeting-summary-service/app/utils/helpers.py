"""
Pure utility functions — no external service dependencies.
"""
import re
from typing import Optional


def chunk_text(text: str, max_chars: int = 12000, overlap: int = 500) -> list[str]:
    """
    Split long transcript into overlapping chunks.
    Tries to split at sentence boundaries.
    """
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chars:
            if current:
                chunks.append(current.strip())
                current = current[-overlap:] + " " + sentence
            else:
                chunks.append(sentence[:max_chars])
                current = sentence[max_chars - overlap:]
        else:
            current = (current + " " + sentence).strip()

    if current.strip():
        chunks.append(current.strip())

    return chunks


def deduplicate_list(items: list[str]) -> list[str]:
    """Remove near-duplicate strings by word overlap."""
    unique: list[str] = []
    for item in items:
        item_words = set(item.lower().split())
        is_dup = any(
            len(item_words & set(existing.lower().split())) / max(len(item_words | set(existing.lower().split())), 1) >= 0.75
            for existing in unique
        )
        if not is_dup:
            unique.append(item)
    return unique


def format_attendees(attendees: list[str]) -> str:
    if not attendees:
        return "Unknown attendees"
    return ", ".join(attendees)


def language_label(code: str) -> str:
    return {"en": "English", "ar": "Arabic"}.get(code, "English")
