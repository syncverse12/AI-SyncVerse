"""
Employee metrics, attendance, tasks, performance reviews ORM models.
"""

import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, Date, DateTime,
    ForeignKey, Text, Index, CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class EmployeeMetrics(Base):
    """Current/snapshot employee metrics for ML features."""

    __tablename__ = "employee_metrics"
    __table_args__ = (
        Index("ix_employee_metrics_employee_id", "employee_id"),
        Index("ix_employee_metrics_snapshot_date", "snapshot_date"),
        CheckConstraint("performance_rating BETWEEN 1 AND 5", name="ck_perf_rating"),
        CheckConstraint("job_satisfaction BETWEEN 1 AND 5", name="ck_job_sat"),
        CheckConstraint("work_life_balance BETWEEN 1 AND 5", name="ck_wlb"),
        CheckConstraint("environment_satisfaction BETWEEN 1 AND 5", name="ck_env_sat"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Survey scores (1-5 scale)
    performance_rating: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    job_satisfaction: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    work_life_balance: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    environment_satisfaction: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    relationship_satisfaction: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Work patterns
    overtime_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    standard_hours: Mapped[float] = mapped_column(Float, nullable=False, default=160.0)
    attendance_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Workload & performance
    workload_score: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)  # 1-10
    team_health_score: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)  # 1-10
    collaboration_score: Mapped[float] = mapped_column(Float, nullable=True, default=7.0)

    # Task metrics
    tasks_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tasks_assigned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missed_deadlines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overdue_task_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Leadership & promotion
    leadership_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    promotion_velocity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # avg years between promos
    training_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="metrics")  # type: ignore


class AttendanceRecord(Base):
    """Daily attendance records."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        Index("ix_attendance_employee_id", "employee_id"),
        Index("ix_attendance_date", "attendance_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hours_worked: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overtime_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    employee: Mapped["Employee"] = relationship("Employee", back_populates="attendance_records")  # type: ignore


class Task(Base):
    """Employee task assignments and completion status."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_employee_id", "employee_id"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_due_date", "due_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # pending, in_progress, completed, overdue, cancelled
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )  # low, medium, high, critical
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 1-5

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    employee: Mapped["Employee"] = relationship("Employee", back_populates="tasks")  # type: ignore


class PerformanceReview(Base):
    """Periodic employee performance reviews."""

    __tablename__ = "performance_reviews"
    __table_args__ = (
        Index("ix_perf_reviews_employee_id", "employee_id"),
        Index("ix_perf_reviews_review_date", "review_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    review_period: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "Q1-2024"

    # Scores
    overall_rating: Mapped[float] = mapped_column(Float, nullable=False)  # 1-5
    technical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    communication_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    leadership_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    teamwork_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    innovation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Promotion recommendation
    promotion_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    employee: Mapped["Employee"] = relationship("Employee", back_populates="performance_reviews")  # type: ignore
