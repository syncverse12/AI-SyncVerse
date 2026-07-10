import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class MeetingSummary(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "echo_meeting_summaries"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    team_name: Mapped[str] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    attendees: Mapped[str] = mapped_column(Text, nullable=True)  # comma-separated
    meeting_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
