import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class TaskStatus(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "echo_tasks"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    team_name: Mapped[str] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status_enum"), default=TaskStatus.todo
    )
    assignee: Mapped[str] = mapped_column(String(255), nullable=True)
    depends_on_team: Mapped[str] = mapped_column(String(120), nullable=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
