"""
SQLAlchemy ORM models — maps domain objects to the risk_engine database.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="planning")

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    budget_usd: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False)

    # Stored as JSON (team, tech stack, etc.)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    risk_reports: Mapped[list[RiskReportORM]] = relationship(
        "RiskReportORM", back_populates="project", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[AlertORM]] = relationship(
        "AlertORM", back_populates="project", cascade="all, delete-orphan"
    )
    metrics_snapshots: Mapped[list[MetricsSnapshot]] = relationship(
        "MetricsSnapshot", back_populates="project", cascade="all, delete-orphan"
    )


class RiskReportORM(Base):
    __tablename__ = "risk_reports"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    report_type: Mapped[str] = mapped_column(String(50))  # pre_project | live_update

    # Core scores — stored flat for fast querying
    overall_risk_score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(20))
    delay_probability: Mapped[float] = mapped_column(Float)
    budget_overrun_probability: Mapped[float] = mapped_column(Float)
    delivery_confidence: Mapped[float] = mapped_column(Float)
    burnout_probability: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)

    # Full report stored as JSON (includes AI reasoning, mitigation, etc.)
    report_json: Mapped[dict] = mapped_column(JSON)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project: Mapped[Project] = relationship("Project", back_populates="risk_reports")


class AlertORM(Base):
    __tablename__ = "risk_alerts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    severity: Mapped[str] = mapped_column(String(20))
    risk_category: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="active")

    title: Mapped[str] = mapped_column(String(500))
    message: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str] = mapped_column(Text)
    ai_insight: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)

    previous_risk_score: Mapped[float] = mapped_column(Float)
    current_risk_score: Mapped[float] = mapped_column(Float)
    delta: Mapped[float] = mapped_column(Float)

    escalation_level: Mapped[int] = mapped_column(Integer, default=1)
    notify_roles: Mapped[list] = mapped_column(JSON, default=list)

    acknowledged_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project: Mapped[Project] = relationship("Project", back_populates="alerts")


class MetricsSnapshot(Base):
    """Point-in-time snapshot of live project metrics — powers the risk timeline."""

    __tablename__ = "metrics_snapshots"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    overall_risk_score: Mapped[float] = mapped_column(Float)
    metrics_json: Mapped[dict] = mapped_column(JSON)

    project: Mapped[Project] = relationship("Project", back_populates="metrics_snapshots")


class HistoricalIncident(Base):
    """Stores past incidents for RAG retrieval and ML training."""

    __tablename__ = "historical_incidents"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    incident_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str] = mapped_column(Text)
    impact: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str] = mapped_column(Text)
    duration_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    was_preventable: Mapped[bool] = mapped_column(Boolean, default=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Qdrant vector ID for retrieval
    vector_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
