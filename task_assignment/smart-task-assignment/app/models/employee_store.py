"""
In-memory employee store with thread-safe async access.
In production, replace with PostgreSQL / Redis backed store.
"""
import asyncio
from typing import Dict, List, Optional
from app.models.schemas import Employee, EmployeeCreate, EmployeeStatusUpdate

_LOCK = asyncio.Lock()

# ── Seed data ────────────────────────────────────────────────────────────────
_EMPLOYEES: Dict[int, Employee] = {
    1: Employee(id=1, name="Ahmed",   track="Backend",  skills=["FastAPI","Redis","Docker","PostgreSQL"],     level="Senior", active_tasks=2,  availability_score=75,  past_success_rate=0.92),
    2: Employee(id=2, name="Sara",    track="Backend",  skills=["FastAPI","Django","Celery","Redis"],          level="Mid",    active_tasks=1,  availability_score=90,  past_success_rate=0.88),
    3: Employee(id=3, name="Omar",    track="Frontend", skills=["React","TypeScript","TailwindCSS","Zustand"], level="Senior", active_tasks=3,  availability_score=55,  past_success_rate=0.90),
    4: Employee(id=4, name="Layla",   track="DevOps",   skills=["Docker","Kubernetes","CI/CD","Terraform"],   level="Lead",   active_tasks=1,  availability_score=85,  past_success_rate=0.95),
    5: Employee(id=5, name="Youssef", track="AI/ML",    skills=["PyTorch","FastAPI","LangChain","OpenCV"],     level="Senior", active_tasks=0,  availability_score=100, past_success_rate=0.89),
    6: Employee(id=6, name="Nour",    track="Backend",  skills=["FastAPI","SQLAlchemy","Alembic"],             level="Junior", active_tasks=4,  availability_score=40,  past_success_rate=0.75),
    7: Employee(id=7, name="Karim",   track="Frontend", skills=["Vue","Nuxt","CSS","GraphQL"],                 level="Mid",    active_tasks=2,  availability_score=70,  past_success_rate=0.82),
    8: Employee(id=8, name="Dina",    track="AI/ML",    skills=["Scikit-learn","Pandas","FastAPI","MLflow"],   level="Mid",    active_tasks=1,  availability_score=88,  past_success_rate=0.86),
}
_NEXT_ID = 9


class EmployeeStore:
    """Async-safe in-memory employee repository."""

    async def get_all(self) -> List[Employee]:
        async with _LOCK:
            return list(_EMPLOYEES.values())

    async def get_by_id(self, employee_id: int) -> Optional[Employee]:
        async with _LOCK:
            return _EMPLOYEES.get(employee_id)

    async def add(self, data: EmployeeCreate) -> Employee:
        global _NEXT_ID
        async with _LOCK:
            emp = Employee(id=_NEXT_ID, **data.dict())
            _EMPLOYEES[_NEXT_ID] = emp
            _NEXT_ID += 1
            return emp

    async def update_status(self, update: EmployeeStatusUpdate) -> Optional[Employee]:
        async with _LOCK:
            emp = _EMPLOYEES.get(update.employee_id)
            if emp is None:
                return None
            data = emp.dict()
            if update.active_tasks is not None:
                data["active_tasks"] = update.active_tasks
            if update.availability_score is not None:
                data["availability_score"] = update.availability_score
            if update.past_success_rate is not None:
                data["past_success_rate"] = update.past_success_rate
            updated = Employee(**data)
            _EMPLOYEES[update.employee_id] = updated
            return updated


# Singleton
employee_store = EmployeeStore()
