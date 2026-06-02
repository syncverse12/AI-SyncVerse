"""
Pure utility functions — no external service dependencies.
"""
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional


def normalize_name(name: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_str.lower().strip())


def names_match(a: str, b: str) -> bool:
    """Check if two name strings likely refer to the same person."""
    na, nb = normalize_name(a), normalize_name(b)
    if na == nb:
        return True
    parts_a = set(na.split())
    parts_b = set(nb.split())
    shared = parts_a & parts_b
    return len(shared) >= 1 and len(shared) >= min(len(parts_a), len(parts_b))


def parse_flexible_date(raw: Optional[str]) -> Optional[str]:
    """
    Parse a date string in multiple formats.
    Returns YYYY-MM-DD string or None.
    """
    if not raw or raw.lower() in ("null", "none", "n/a", ""):
        return None
    formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y",
        "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def chunk_text(text: str, max_chars: int = 8000, overlap: int = 300) -> list[str]:
    """Split long transcript into overlapping chunks for LLM context limits."""
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


def extract_person_names_regex(text: str) -> list[str]:
    """
    Simple regex-based name extraction as fallback when spaCy is unavailable.
    Finds capitalized two-word sequences that look like names.
    """
    pattern = r"\b([A-Z][a-z]{1,15})\s+([A-Z][a-z]{1,20})\b"
    matches = re.findall(pattern, text)
    full_names = [f"{first} {last}" for first, last in matches]
    single_pattern = r"\b([A-Z][a-z]{2,15})\b(?:\s+(?:will|should|must|needs? to|is going to|has to))"
    singles = re.findall(single_pattern, text)
    return list(dict.fromkeys(full_names + singles))


def today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")
