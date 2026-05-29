"""
Promotion Recommendation & Team Risk Analysis API Endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db
from app.services.attrition_service import PromotionService, TeamRiskService
from app.schemas.schemas import PromotionResponse, TeamRiskResponse, ErrorResponse
from app.core.exceptions import (
    EmployeeNotFoundException,
    TeamNotFoundException,
    InsufficientDataException,
    ModelNotLoadedException,
    PredictionFailedException,
)

# ──────────────────────────────────────────────
# Promotion Router
# ──────────────────────────────────────────────

promotion_router = APIRouter(prefix="/promotion", tags=["Promotion Recommendation"])


@promotion_router.post(
    "/predict/{employee_id}",
    response_model=PromotionResponse,
    summary="Predict promotion readiness for an employee",
    responses={
        200: {"description": "Promotion recommendation with reasoning and development areas"},
        404: {"description": "Employee not found", "model": ErrorResponse},
        422: {"description": "Insufficient data", "model": ErrorResponse},
        503: {"description": "ML model not available", "model": ErrorResponse},
    },
)
async def predict_promotion(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
) -> PromotionResponse:
    """
    Assess promotion readiness for an employee.

    Returns:
    - **promotion_readiness_score**: 0-100 composite score
    - **promotion_recommended**: Boolean recommendation
    - **recommended_role**: Suggested next role/level
    - **promotion_reasoning**: Key factors driving the recommendation
    - **top_strengths**: Employee's strongest performance areas
    - **development_areas**: Areas requiring development before promotion
    """
    service = PromotionService(db)
    try:
        result = await service.predict_promotion(employee_id)
        logger.info(
            f"Promotion prediction complete | employee={employee_id} | "
            f"score={result.promotion_readiness_score:.1f} | "
            f"recommended={result.promotion_recommended}"
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
        logger.error(f"Unexpected error in promotion prediction: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


# ──────────────────────────────────────────────
# Team Risk Router
# ──────────────────────────────────────────────

team_router = APIRouter(prefix="/team-risk", tags=["Team Risk Analysis"])


@team_router.get(
    "/{team_id}",
    response_model=TeamRiskResponse,
    summary="Analyze attrition risk across an entire team",
    responses={
        200: {"description": "Team-level risk aggregation with burnout indicators"},
        404: {"description": "Team not found", "model": ErrorResponse},
    },
)
async def analyze_team_risk(
    team_id: str,
    db: AsyncSession = Depends(get_db),
) -> TeamRiskResponse:
    """
    Compute team-level attrition risk analysis.

    Returns:
    - **average_attrition_probability**: Team-wide risk average
    - **high_risk_count**: Number of employees at high risk
    - **burnout_indicator**: Team burnout severity (Low/Moderate/High/Critical)
    - **workload_distribution**: Distribution of workload across team
    - **top_risk_employees**: Top 5 employees by attrition probability
    - **team_recommendations**: Actionable team-level interventions
    """
    service = TeamRiskService(db)
    try:
        result = await service.analyze_team(team_id)
        logger.info(
            f"Team risk analysis complete | team={team_id} | "
            f"avg_prob={result.average_attrition_probability:.2%} | "
            f"burnout={result.burnout_indicator}"
        )
        return result

    except TeamNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)

    except Exception as exc:
        logger.error(f"Unexpected error in team risk analysis: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during team analysis.",
        )
