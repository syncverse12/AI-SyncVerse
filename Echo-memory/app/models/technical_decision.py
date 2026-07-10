import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class TechnicalDecision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "echo_technical_decisions"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    team_name: Mapped[str] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=True)
    alternatives_considered: Mapped[str] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(255), nullable=True)
