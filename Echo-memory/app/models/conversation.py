import enum
import uuid

from sqlalchemy import Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class MessageRole(str, enum.Enum):
    user = "user"
    echo = "echo"


class ConversationMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Persisted chat history, kept per project *and* per user so Echo can
    hold a coherent conversation without mixing contexts between people."""

    __tablename__ = "echo_conversation_messages"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole, name="message_role_enum"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(60), nullable=True)
