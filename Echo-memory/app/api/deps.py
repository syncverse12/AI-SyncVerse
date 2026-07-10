from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.echo_service import EchoService
from app.services.memory_service import MemoryService
from app.services.summary_service import SummaryService

# Re-exported for convenience in route modules.
__all__ = ["get_db", "get_echo_service", "get_memory_service", "get_summary_service"]


def get_echo_service(db: Session) -> EchoService:
    return EchoService(db)


def get_memory_service(db: Session) -> MemoryService:
    return MemoryService(db)


def get_summary_service(db: Session) -> SummaryService:
    return SummaryService(db)
