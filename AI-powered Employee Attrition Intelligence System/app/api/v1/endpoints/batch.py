"""
Batch Prediction Endpoint.
Trigger attrition predictions for multiple employees in one request.
"""

from __future__ import annotations
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db
from app.services.attrition_service import AttritionService
from app.core.exceptions import EmployeeNotFoundException, InsufficientDataException

router = APIRouter(prefix="/batch", tags=["Batch Operations"])


class BatchAttritionRequest(BaseModel):
    employee_ids: List[str] = Field(..., min_length=1, max_length=100)


class BatchAttritionResult(BaseModel):
    employee_id: str
    success: bool
    attrition_probability: float | None = None
    risk_level: str | None = None
    error: str | None = None


class BatchAttritionResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[BatchAttritionResult]


@router.post(
    "/attrition/predict",
    response_model=BatchAttritionResponse,
    summary="Batch attrition prediction for multiple employees",
    description="Run attrition predictions for up to 100 employees in a single request.",
)
async def batch_predict_attrition(
    payload: BatchAttritionRequest,
    db: AsyncSession = Depends(get_db),
) -> BatchAttritionResponse:
    """
    Predict attrition risk for a list of employee IDs.
    Continues on individual failures — all results are returned.
    """
    service = AttritionService(db)
    results: List[BatchAttritionResult] = []

    for emp_id in payload.employee_ids:
        try:
            prediction = await service.predict_attrition(emp_id, trigger="batch")
            results.append(
                BatchAttritionResult(
                    employee_id=emp_id,
                    success=True,
                    attrition_probability=prediction.attrition_probability,
                    risk_level=prediction.risk_level,
                )
            )
        except (EmployeeNotFoundException, InsufficientDataException) as exc:
            results.append(
                BatchAttritionResult(
                    employee_id=emp_id,
                    success=False,
                    error=exc.message,
                )
            )
        except Exception as exc:
            logger.error(f"Batch prediction failed for {emp_id}: {exc}")
            results.append(
                BatchAttritionResult(
                    employee_id=emp_id,
                    success=False,
                    error="Prediction failed due to an internal error.",
                )
            )

    succeeded = sum(1 for r in results if r.success)
    failed = len(results) - succeeded

    logger.info(
        f"Batch attrition prediction complete | "
        f"total={len(results)} | succeeded={succeeded} | failed={failed}"
    )

    return BatchAttritionResponse(
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


@router.post(
    "/attrition/predict/team/{team_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger background batch prediction for all employees in a team",
)
async def trigger_team_batch(
    team_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Trigger asynchronous background recalculation for all employees in a team.
    Returns immediately with 202 Accepted.
    """
    from app.repositories.employee_repository import EmployeeRepository

    repo = EmployeeRepository(db)
    employees = await repo.get_by_team(team_id)

    if not employees:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active employees found for team '{team_id}'.",
        )

    employee_ids = [str(e.id) for e in employees]

    async def run_batch():
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_db:
            svc = AttritionService(bg_db)
            for eid in employee_ids:
                try:
                    await svc.predict_attrition(eid, trigger="batch_team")
                except Exception as exc:
                    logger.warning(f"Background batch failed for {eid}: {exc}")
            await bg_db.commit()
        logger.info(f"Background team batch complete for team {team_id}")

    background_tasks.add_task(run_batch)

    return {
        "status": "accepted",
        "team_id": team_id,
        "employees_queued": len(employee_ids),
        "message": "Batch predictions are being processed in the background.",
    }
