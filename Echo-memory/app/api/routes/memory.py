from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.schemas.memory import MemoryCreate, MemoryOut
from app.services.memory_service import MemoryService

logger = get_logger(__name__)
router = APIRouter(tags=["Memory"])


@router.post("/memory", response_model=MemoryOut, status_code=201, summary="Manually record a memory")
def create_memory(payload: MemoryCreate, db: Session = Depends(get_db)) -> MemoryOut:
    """Manually add a memory. In most cases memories should be created
    automatically via AutoMemoryCollector as platform events occur, but
    this endpoint exists for manual entry, imports, and integrations."""
    try:
        service = MemoryService(db)
        memory = service.create_memory(payload)
        return MemoryOut.model_validate(memory)
    except Exception as exc:
        logger.exception("Failed to create memory for project=%s", payload.project_id)
        raise HTTPException(status_code=500, detail="Failed to record memory.") from exc
