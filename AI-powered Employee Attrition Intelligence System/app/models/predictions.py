"""
Attrition and Promotion prediction result ORM models.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Float, Boolean, DateTime,
    ForeignKey, Text, Index, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class AttritionPrediction(Base):
    """Stores attrition prediction results with history."""

    __tablename__ = "attrition_predictions"
    __table_args__ = (
        Index("ix_attrition_pred_employee_id", "employee_id"),
        Index("ix_attrition_pred_risk_level", "risk_level"),
        Index("ix_attrition_pred_predicted_at", "predicted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )

    # Prediction results
    attrition_probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # Low, Medium, High
    top_risk_factors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    shap_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Metadata
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trigger: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )  # manual, scheduled, batch
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    employee: Mapped["Employee"] = relationship(  # type: ignore
        "Employee", back_populates="attrition_predictions"
    )


class PromotionPrediction(Base):
    """Stores promotion recommendation results with history."""

    __tablename__ = "promotion_predictions"
    __table_args__ = (
        Index("ix_promotion_pred_employee_id", "employee_id"),
        Index("ix_promotion_pred_recommended", "promotion_recommended"),
        Index("ix_promotion_pred_predicted_at", "predicted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )

    # Prediction results
    promotion_readiness_score: Mapped[float] = mapped_column(Float, nullable=False)
    promotion_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recommended_role: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    promotion_reasoning: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    top_strengths: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    development_areas: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Metadata
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    employee: Mapped["Employee"] = relationship(  # type: ignore
        "Employee", back_populates="promotion_predictions"
    )
