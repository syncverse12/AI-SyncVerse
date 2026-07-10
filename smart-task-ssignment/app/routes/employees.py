"""
Employee routes
  GET  /employees
  POST /add-employee
  POST /update-employee-status
"""
import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import EmployeeCreate, EmployeeStatusUpdate
from app.models.employee_store import employee_store
from app.services.realtime_engine import realtime_engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["employees"])


@router.get("/employees", summary="List all employees")
async def list_employees():
    employees = await employee_store.get_all()
    return {"count": len(employees), "employees": [e.model_dump() for e in employees]}


@router.post("/add-employee", summary="Add a new employee", status_code=201)
async def add_employee(data: EmployeeCreate):
    emp = await employee_store.add(data)
    logger.info(f"Employee added  id={emp.id}  name={emp.name}")
    return {"message": "Employee added", "employee": emp.model_dump()}


@router.post("/update-employee-status", summary="Update employee workload / availability")
async def update_employee_status(update: EmployeeStatusUpdate):
    emp = await employee_store.update_status(update)
    if emp is None:
        raise HTTPException(status_code=404, detail=f"Employee {update.employee_id} not found")

    # Broadcast real-time update to all WebSocket clients
    changes = update.dict(exclude_none=True, exclude={"employee_id"})
    await realtime_engine.notify_employee_updated(update.employee_id, changes)

    return {"message": "Employee status updated", "employee": emp.model_dump()}
