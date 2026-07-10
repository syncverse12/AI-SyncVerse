import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class TeamAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Which member belongs to which team, on which project."""

    __tablename__ = "echo_team_assignments"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    team_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    member_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=True)
