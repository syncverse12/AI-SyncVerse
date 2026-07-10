import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    def __init__(self, db: Session):
        super().__init__(db, Task)

    def get_blocked(self, project_id: uuid.UUID) -> List[Task]:
        stmt = select(Task).where(Task.project_id == project_id, Task.status == TaskStatus.blocked)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_status(self, project_id: uuid.UUID, status: TaskStatus) -> List[Task]:
        stmt = select(Task).where(Task.project_id == project_id, Task.status == status)
        return list(self.db.execute(stmt).scalars().all())
