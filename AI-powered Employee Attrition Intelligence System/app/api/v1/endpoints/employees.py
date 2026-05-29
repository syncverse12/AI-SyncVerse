"""
Employee Management Endpoints.
CRUD for employees and metrics — used by the SyncVerse admin/dashboard.
"""

from __future__ import annotations
import uuid
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db
from app.models.employee import Employee
from app.models.metrics import EmployeeMetrics
from app.schemas.schemas import (
    EmployeeCreate, EmployeeResponse,
    EmployeeMetricsCreate, PaginatedResponse, ErrorResponse,
)
from app.core.exceptions import EmployeeNotFoundException

router = APIRouter(prefix="/employees", tags=["Employee Management"])


# ──────────────────────────────────────────────
# Employee CRUD
# ──────────────────────────────────────────────

@router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new employee",
)
async def create_employee(
    payload: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
) -> EmployeeResponse:
    """Create a new employee record."""
    # Check for duplicate email
    existing = await db.execute(
        select(Employee).where(Employee.email == payload.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee with email '{payload.email}' already exists.",
        )

    employee = Employee(
        id=uuid.uuid4(),
        **payload.model_dump(),
    )
    db.add(employee)
    await db.flush()
    await db.refresh(employee)
    logger.info(f"Created employee: {employee.employee_code}")
    return employee


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Get employee by ID",
    responses={404: {"model": ErrorResponse}},
)
async def get_employee(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
) -> EmployeeResponse:
    """Fetch a single employee by UUID."""
    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee ID format.")

    result = await db.execute(select(Employee).where(Employee.id == emp_uuid))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee '{employee_id}' not found.",
        )
    return employee


@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="List employees (paginated)",
)
async def list_employees(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    department: Optional[str] = Query(default=None),
    team_id: Optional[str] = Query(default=None),
    is_active: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """List employees with optional filtering and pagination."""
    filters = [Employee.is_active == is_active]
    if department:
        filters.append(Employee.department == department)
    if team_id:
        filters.append(Employee.team_id == team_id)

    # Count
    count_stmt = select(func.count(Employee.id)).where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    # Fetch page
    offset = (page - 1) * page_size
    stmt = (
        select(Employee)
        .where(*filters)
        .offset(offset)
        .limit(page_size)
        .order_by(Employee.created_at.desc())
    )
    result = await db.execute(stmt)
    employees = result.scalars().all()

    return PaginatedResponse(
        items=[EmployeeResponse.model_validate(e) for e in employees],
        total=total,
        page=page,
        page_size=page_size,
        pages=-(-total // page_size),  # ceiling division
    )


@router.patch(
    "/{employee_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark employee as inactive (left company)",
)
async def deactivate_employee(
    employee_id: str,
    left_date: Optional[date] = None,
    voluntary: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mark an employee as no longer active."""
    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee ID format.")

    result = await db.execute(select(Employee).where(Employee.id == emp_uuid))
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    employee.is_active = False
    employee.left_date = left_date or date.today()
    employee.left_voluntarily = voluntary
    await db.flush()
    logger.info(f"Deactivated employee {employee_id}")


# ──────────────────────────────────────────────
# Employee Metrics CRUD
# ──────────────────────────────────────────────

@router.post(
    "/{employee_id}/metrics",
    status_code=status.HTTP_201_CREATED,
    summary="Add a metrics snapshot for an employee",
    responses={404: {"model": ErrorResponse}},
)
async def create_metrics(
    employee_id: str,
    payload: EmployeeMetricsCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Add a new metrics snapshot for an employee.
    The latest snapshot is used for ML predictions.
    """
    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee ID format.")

    result = await db.execute(select(Employee).where(Employee.id == emp_uuid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Employee not found.")

    metrics = EmployeeMetrics(
        id=uuid.uuid4(),
        employee_id=emp_uuid,
        **payload.model_dump(),
    )
    db.add(metrics)
    await db.flush()

    logger.info(f"Metrics snapshot created for employee {employee_id}")
    return {"id": str(metrics.id), "employee_id": employee_id, "snapshot_date": str(metrics.snapshot_date)}


@router.get(
    "/{employee_id}/metrics/latest",
    summary="Get the most recent metrics for an employee",
    responses={404: {"model": ErrorResponse}},
)
async def get_latest_metrics(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the most recent metrics snapshot for an employee."""
    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee ID format.")

    from sqlalchemy import desc
    stmt = (
        select(EmployeeMetrics)
        .where(EmployeeMetrics.employee_id == emp_uuid)
        .order_by(desc(EmployeeMetrics.snapshot_date))
        .limit(1)
    )
    result = await db.execute(stmt)
    metrics = result.scalar_one_or_none()
    if not metrics:
        raise HTTPException(status_code=404, detail="No metrics found for this employee.")

    # Return as dict (full metrics payload)
    return {
        "id": str(metrics.id),
        "employee_id": employee_id,
        "snapshot_date": str(metrics.snapshot_date),
        "performance_rating": metrics.performance_rating,
        "job_satisfaction": metrics.job_satisfaction,
        "work_life_balance": metrics.work_life_balance,
        "environment_satisfaction": metrics.environment_satisfaction,
        "overtime_hours": metrics.overtime_hours,
        "attendance_rate": metrics.attendance_rate,
        "workload_score": metrics.workload_score,
        "team_health_score": metrics.team_health_score,
        "tasks_completed": metrics.tasks_completed,
        "tasks_assigned": metrics.tasks_assigned,
        "missed_deadlines": metrics.missed_deadlines,
        "overdue_task_ratio": metrics.overdue_task_ratio,
        "collaboration_score": metrics.collaboration_score,
        "leadership_score": metrics.leadership_score,
        "promotion_velocity": metrics.promotion_velocity,
        "training_hours": metrics.training_hours,
    }
