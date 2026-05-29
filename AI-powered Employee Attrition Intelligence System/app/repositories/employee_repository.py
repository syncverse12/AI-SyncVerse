"""
Employee Repository: data access layer for employee-related queries.
"""

from __future__ import annotations
import uuid
from datetime import date
from typing import Optional, List

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.employee import Employee
from app.models.metrics import EmployeeMetrics
from app.models.predictions import AttritionPrediction, PromotionPrediction
from app.core.exceptions import EmployeeNotFoundException, DatabaseException
from loguru import logger


class EmployeeRepository:
    """CRUD + query operations for employees."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, employee_id: str) -> Employee:
        """Fetch employee by UUID string. Raises EmployeeNotFoundException if not found."""
        try:
            emp_uuid = uuid.UUID(employee_id)
        except ValueError:
            raise EmployeeNotFoundException(employee_id)

        stmt = (
            select(Employee)
            .where(Employee.id == emp_uuid)
            .options(
                selectinload(Employee.metrics),
                selectinload(Employee.performance_reviews),
            )
        )
        result = await self.db.execute(stmt)
        employee = result.scalar_one_or_none()
        if employee is None:
            raise EmployeeNotFoundException(employee_id)
        return employee

    async def get_by_team(self, team_id: str) -> List[Employee]:
        """Fetch all active employees in a team."""
        stmt = (
            select(Employee)
            .where(
                and_(Employee.team_id == team_id, Employee.is_active == True)
            )
            .options(selectinload(Employee.metrics))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_metrics(
        self, employee_id: uuid.UUID
    ) -> Optional[EmployeeMetrics]:
        """Get the most recent metrics snapshot for an employee."""
        stmt = (
            select(EmployeeMetrics)
            .where(EmployeeMetrics.employee_id == employee_id)
            .order_by(desc(EmployeeMetrics.snapshot_date))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self, limit: int = 1000, offset: int = 0) -> List[Employee]:
        """Fetch all active employees (paginated)."""
        stmt = (
            select(Employee)
            .where(Employee.is_active == True)
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_count_active(self) -> int:
        from sqlalchemy import func
        stmt = select(func.count(Employee.id)).where(Employee.is_active == True)
        result = await self.db.execute(stmt)
        return result.scalar_one()


class PredictionRepository:
    """CRUD for attrition and promotion predictions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_attrition_prediction(
        self, prediction: AttritionPrediction
    ) -> AttritionPrediction:
        """
        Save new prediction and mark previous ones as not-latest.
        """
        # Mark old predictions as not latest
        old_stmt = (
            select(AttritionPrediction)
            .where(
                and_(
                    AttritionPrediction.employee_id == prediction.employee_id,
                    AttritionPrediction.is_latest == True,
                )
            )
        )
        result = await self.db.execute(old_stmt)
        for old in result.scalars().all():
            old.is_latest = False

        self.db.add(prediction)
        await self.db.flush()
        return prediction

    async def get_latest_attrition(
        self, employee_id: uuid.UUID
    ) -> Optional[AttritionPrediction]:
        stmt = (
            select(AttritionPrediction)
            .where(
                and_(
                    AttritionPrediction.employee_id == employee_id,
                    AttritionPrediction.is_latest == True,
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def save_promotion_prediction(
        self, prediction: PromotionPrediction
    ) -> PromotionPrediction:
        old_stmt = (
            select(PromotionPrediction)
            .where(
                and_(
                    PromotionPrediction.employee_id == prediction.employee_id,
                    PromotionPrediction.is_latest == True,
                )
            )
        )
        result = await self.db.execute(old_stmt)
        for old in result.scalars().all():
            old.is_latest = False

        self.db.add(prediction)
        await self.db.flush()
        return prediction

    async def get_latest_promotion(
        self, employee_id: uuid.UUID
    ) -> Optional[PromotionPrediction]:
        stmt = (
            select(PromotionPrediction)
            .where(
                and_(
                    PromotionPrediction.employee_id == employee_id,
                    PromotionPrediction.is_latest == True,
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_attrition_history(
        self, employee_id: uuid.UUID, limit: int = 10
    ) -> List[AttritionPrediction]:
        stmt = (
            select(AttritionPrediction)
            .where(AttritionPrediction.employee_id == employee_id)
            .order_by(desc(AttritionPrediction.predicted_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
