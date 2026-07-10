import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.risk import Risk, RiskSeverity
from app.repositories.base import BaseRepository


class RiskRepository(BaseRepository[Risk]):
    def __init__(self, db: Session):
        super().__init__(db, Risk)

    def get_high_severity(self, project_id: uuid.UUID) -> List[Risk]:
        stmt = select(Risk).where(
            Risk.project_id == project_id,
            Risk.severity.in_([RiskSeverity.high, RiskSeverity.critical]),
        )
        return list(self.db.execute(stmt).scalars().all())
