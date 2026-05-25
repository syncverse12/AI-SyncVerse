"""
Shared utility functions used across services.
"""
import re
from datetime import datetime, date
from typing import Optional
import unicodedata


def normalize_name(name: str) -> str:
    """
    Normalize a person name for comparison.
    Strips diacritics, lowercases, collapses whitespace.
    """
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_name.lower().strip())


def names_match(a: str, b: str) -> bool:
    """Check if two name strings refer to the same person."""
    na, nb = normalize_name(a), normalize_name(b)
    if na == nb:
        return True
    parts_a = set(na.split())
    parts_b = set(nb.split())
    shared = parts_a & parts_b
    return len(shared) >= 1 and len(shared) >= min(len(parts_a), len(parts_b))


def chunk_text(text: str, max_chars: int = 6000, overlap: int = 200) -> list[str]:
    """
    Split long text into overlapping chunks for LLM processing.
    Splits at sentence boundaries where possible.
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


def parse_flexible_date(raw: str) -> Optional[datetime]:
    """Parse date strings in multiple formats, return datetime or None."""
    if not raw or raw.lower() in ("null", "none", "n/a", ""):
        return None

    formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y",
        "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def sanitize_for_json(obj):
    """Recursively convert non-serializable types for JSON output."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(i) for i in obj]
    return obj


def truncate(text: str, max_len: int = 300, suffix: str = "...") -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix
