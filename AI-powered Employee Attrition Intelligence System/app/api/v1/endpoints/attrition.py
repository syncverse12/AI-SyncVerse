"""
Attrition Prediction API Endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db
from app.services.attrition_service import AttritionService
from app.schemas.schemas import AttritionPredictionResponse, ErrorResponse
from app.core.exceptions import (
    EmployeeNotFoundException,
    InsufficientDataException,
    ModelNotLoadedException,
    PredictionFailedException,
)

router = APIRouter(prefix="/attrition", tags=["Attrition Prediction"])


@router.post(
    "/predict/{employee_id}",
    response_model=AttritionPredictionResponse,
    summary="Predict employee attrition risk",
    responses={
        200: {"description": "Attrition prediction with explanations and recommendations"},
        404: {"description": "Employee not found", "model": ErrorResponse},
        422: {"description": "Insufficient data for prediction", "model": ErrorResponse},
        503: {"description": "ML model not available", "model": ErrorResponse},
    },
)
async def predict_attrition(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
) -> AttritionPredictionResponse:
    """
    Predict attrition risk for a single employee.

    Returns:
    - **attrition_probability**: 0.0 (no risk) to 1.0 (certain to leave)
    - **risk_level**: Low / Medium / High
    - **top_risk_factors**: SHAP-based feature contributions ranked by impact
    - **recommendations**: Prioritized retention actions
    - **explanation_summary**: Human-readable narrative
    """
    service = AttritionService(db)
    try:
        result = await service.predict_attrition(employee_id, trigger="manual")
        logger.info(
            f"Attrition prediction complete | employee={employee_id} | "
            f"risk={result.risk_level} | prob={result.attrition_probability:.2%}"
        )
        return result

    except EmployeeNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)

    except InsufficientDataException as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message)

    except ModelNotLoadedException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{exc.message}. Run training pipeline first.",
        )

    except PredictionFailedException as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message)

    except Exception as exc:
        logger.error(f"Unexpected error in attrition prediction: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during prediction.",
        )
