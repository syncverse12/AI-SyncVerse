"""
API v1 Router — aggregates all endpoint routers.
"""

from fastapi import APIRouter
from app.api.v1.endpoints.attrition import router as attrition_router
from app.api.v1.endpoints.promotion_team import promotion_router, team_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.employees import router as employees_router
from app.api.v1.endpoints.prediction_history import router as history_router
from app.api.v1.endpoints.batch import router as batch_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(attrition_router)
api_router.include_router(promotion_router)
api_router.include_router(team_router)
api_router.include_router(employees_router)
api_router.include_router(history_router)
api_router.include_router(batch_router)

# Health at root level (no /api/v1 prefix)
root_router = APIRouter()
root_router.include_router(health_router)
