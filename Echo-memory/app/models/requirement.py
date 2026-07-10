import enum
import uuid

from sqlalchemy import Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class RequirementStatus(str, enum.Enum):
    proposed = "proposed"
    approved = "approved"
    changed = "changed"
    deprecated = "deprecated"


class Requirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "echo_requirements"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[RequirementStatus] = mapped_column(
        SAEnum(RequirementStatus, name="requirement_status_enum"),
        default=RequirementStatus.proposed,
    )
    owner: Mapped[str] = mapped_column(String(255), nullable=True)
