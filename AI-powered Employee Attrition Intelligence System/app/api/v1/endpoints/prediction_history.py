"""
Prediction History Endpoints.
Retrieve historical attrition and promotion predictions for an employee.
"""

from __future__ import annotations
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.predictions import AttritionPrediction, PromotionPrediction

router = APIRouter(prefix="/predictions", tags=["Prediction History"])


@router.get(
    "/attrition/{employee_id}/history",
    summary="Get attrition prediction history for an employee",
)
async def attrition_history(
    employee_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """
    Returns the last N attrition predictions for an employee,
    ordered newest first. Useful for trend dashboards.
    """
    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee ID format.")

    stmt = (
        select(AttritionPrediction)
        .where(AttritionPrediction.employee_id == emp_uuid)
        .order_by(desc(AttritionPrediction.predicted_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "attrition_probability": r.attrition_probability,
            "risk_level": r.risk_level,
            "trigger": r.trigger,
            "is_latest": r.is_latest,
            "predicted_at": r.predicted_at.isoformat(),
        }
        for r in records
    ]


@router.get(
    "/promotion/{employee_id}/history",
    summary="Get promotion prediction history for an employee",
)
async def promotion_history(
    employee_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """
    Returns the last N promotion predictions for an employee,
    ordered newest first.
    """
    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee ID format.")

    stmt = (
        select(PromotionPrediction)
        .where(PromotionPrediction.employee_id == emp_uuid)
        .order_by(desc(PromotionPrediction.predicted_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "promotion_readiness_score": r.promotion_readiness_score,
            "promotion_recommended": r.promotion_recommended,
            "recommended_role": r.recommended_role,
            "trigger": r.trigger,
            "is_latest": r.is_latest,
            "predicted_at": r.predicted_at.isoformat(),
        }
        for r in records
    ]


@router.get(
    "/attrition/high-risk",
    summary="Get all currently high-risk employees (latest predictions)",
)
async def all_high_risk(
    risk_level: str = Query(default="High", description="Low, Medium, or High"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """
    Fetch all employees with the given risk level from their latest prediction.
    Useful for bulk HR dashboards.
    """
    stmt = (
        select(AttritionPrediction)
        .where(
            AttritionPrediction.is_latest == True,
            AttritionPrediction.risk_level == risk_level,
        )
        .order_by(desc(AttritionPrediction.attrition_probability))
        .limit(limit)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return [
        {
            "employee_id": str(r.employee_id),
            "attrition_probability": r.attrition_probability,
            "risk_level": r.risk_level,
            "predicted_at": r.predicted_at.isoformat(),
            "top_risk_factors": r.top_risk_factors,
        }
        for r in records
    ]
