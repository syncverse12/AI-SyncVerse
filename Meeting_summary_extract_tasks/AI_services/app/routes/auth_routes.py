from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from AI_services.app.database.session import get_db
from AI_services.app.models.models import Employee
from AI_services.app.schemas.schemas import EmployeeCreate, EmployeeOut, TokenOut, LoginIn
from AI_services.app.utils.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=EmployeeOut, status_code=201)
async def register(body: EmployeeCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Employee).where(Employee.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    emp = Employee(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        department=body.department,
        role=body.role,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Employee).where(Employee.email == body.email))
    emp = result.scalar_one_or_none()
    if not emp or not verify_password(body.password, emp.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(subject=emp.id)
    return TokenOut(access_token=token)


@router.get("/me", response_model=EmployeeOut)
async def me(
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(lambda: None),
):
    from AI_services.app.utils.auth import get_current_employee
    return current_employee
