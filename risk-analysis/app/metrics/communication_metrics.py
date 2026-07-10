"""Deterministic meeting-frequency metrics (the raw count only - the
judgment of whether that count signals risk belongs to the AI layer,
since 'enough meetings' is context-dependent, not a fixed rule)."""

from datetime import datetime, timezone, timedelta
from typing import List
from app.schemas.context_schema import MeetingItem


def meeting_frequency(meetings: List[MeetingItem], lookback_days: int = 14) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    return sum(1 for m in meetings if m.start_time and m.start_time >= cutoff)


def communication_summary(meetings: List[MeetingItem], lookback_days: int = 14) -> dict:
    return {
        "meetings_last_period": meeting_frequency(meetings, lookback_days),
        "lookback_days": lookback_days,
    }
