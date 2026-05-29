"""
Employee and related ORM models.
"""

import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String, Integer, Float, Boolean, Date, DateTime,
    ForeignKey, Text, Index, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import enum

from app.db.session import Base


class DepartmentEnum(str, enum.Enum):
    ENGINEERING = "Engineering"
    PRODUCT = "Product"
    SALES = "Sales"
    MARKETING = "Marketing"
    HR = "HR"
    FINANCE = "Finance"
    OPERATIONS = "Operations"
    CUSTOMER_SUCCESS = "Customer Success"
    DATA = "Data"
    DESIGN = "Design"


class JobLevelEnum(str, enum.Enum):
    JUNIOR = "Junior"
    MID = "Mid"
    SENIOR = "Senior"
    LEAD = "Lead"
    MANAGER = "Manager"
    DIRECTOR = "Director"
    VP = "VP"
    C_LEVEL = "C-Level"


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        Index("ix_employees_department", "department"),
        Index("ix_employees_team_id", "team_id"),
        Index("ix_employees_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Demographics
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Job info
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    job_role: Mapped[str] = mapped_column(String(150), nullable=False)
    job_level: Mapped[str] = mapped_column(String(50), nullable=False)
    team_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True
    )

    # Compensation
    monthly_income: Mapped[float] = mapped_column(Float, nullable=False)
    salary_hike_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Tenure
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    years_at_company: Mapped[float] = mapped_column(Float, nullable=False)
    years_in_current_role: Mapped[float] = mapped_column(Float, nullable=True, default=0.0)
    years_since_last_promotion: Mapped[float] = mapped_column(Float, nullable=True, default=0.0)
    years_with_curr_manager: Mapped[float] = mapped_column(Float, nullable=True, default=0.0)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    left_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    left_voluntarily: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    metrics: Mapped[list["EmployeeMetrics"]] = relationship(
        "EmployeeMetrics", back_populates="employee", cascade="all, delete-orphan"
    )
    performance_reviews: Mapped[list["PerformanceReview"]] = relationship(
        "PerformanceReview", back_populates="employee", cascade="all, delete-orphan"
    )
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        "AttendanceRecord", back_populates="employee", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="employee", cascade="all, delete-orphan"
    )
    attrition_predictions: Mapped[list["AttritionPrediction"]] = relationship(
        "AttritionPrediction", back_populates="employee", cascade="all, delete-orphan"
    )
    promotion_predictions: Mapped[list["PromotionPrediction"]] = relationship(
        "PromotionPrediction", back_populates="employee", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Employee {self.employee_code}: {self.first_name} {self.last_name}>"
