import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class Comment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "echo_comments"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=True)  # e.g. "task", "risk"
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=True)
    author: Mapped[str] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
