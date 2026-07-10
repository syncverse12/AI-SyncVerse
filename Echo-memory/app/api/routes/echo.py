from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.schemas.chat import EchoChatRequest, EchoChatResponse
from app.services.echo_service import EchoService

logger = get_logger(__name__)
router = APIRouter(tags=["Echo Chat"])


@router.post("/chat", response_model=EchoChatResponse, summary="Talk to Echo")
def chat_with_echo(payload: EchoChatRequest, db: Session = Depends(get_db)) -> EchoChatResponse:
    """The single entry point users talk to Echo through.

    Echo automatically determines whether the question needs project
    memory, technical advice, project-management analysis, or
    documentation generation, and answers accordingly.
    """
    try:
        service = EchoService(db)
        return service.chat(
            project_id=payload.project_id, user_id=payload.user_id, message=payload.message
        )
    except Exception as exc:
        logger.exception("Echo chat failed for project=%s user=%s", payload.project_id, payload.user_id)
        raise HTTPException(status_code=500, detail="Echo was unable to process this message.") from exc
