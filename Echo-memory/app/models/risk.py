import enum
import uuid

from sqlalchemy import Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class RiskSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Risk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "echo_risks"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    team_name: Mapped[str] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    severity: Mapped[RiskSeverity] = mapped_column(
        SAEnum(RiskSeverity, name="risk_severity_enum"), default=RiskSeverity.medium
    )
    mitigation: Mapped[str] = mapped_column(Text, nullable=True)
    reported_by: Mapped[str] = mapped_column(String(255), nullable=True)
