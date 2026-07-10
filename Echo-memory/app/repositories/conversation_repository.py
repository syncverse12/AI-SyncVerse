import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import ConversationMessage, MessageRole
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[ConversationMessage]):
    def __init__(self, db: Session):
        super().__init__(db, ConversationMessage)

    def get_recent(
        self, project_id: uuid.UUID, user_id: str, limit: int = 12
    ) -> List[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(
                ConversationMessage.project_id == project_id,
                ConversationMessage.user_id == user_id,
            )
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(self.db.execute(stmt).scalars().all())
        return list(reversed(messages))

    def add_message(
        self,
        project_id: uuid.UUID,
        user_id: str,
        role: MessageRole,
        content: str,
        mode: str | None = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            project_id=project_id, user_id=user_id, role=role, content=content, mode=mode
        )
        return self.create(message)
