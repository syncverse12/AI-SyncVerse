from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from AI_services.app.database.session import get_db
from AI_services.app.models.models import Employee
from AI_services.app.utils.auth import get_current_employee
from AI_services.app.controllers.meeting_controller import meeting_controller, employee_controller

router = APIRouter(prefix="/stats", tags=["Analytics"])


@router.get("/meeting/{meeting_id}")
async def meeting_stats(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    """Meeting-level stats: task counts, transcript length, assignee breakdown."""
    meeting = await meeting_controller.get_meeting_with_attendees(meeting_id, db)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.host_id != current_employee.id:
        raise HTTPException(status_code=403, detail="Host only")
    return await meeting_controller.get_meeting_stats(meeting_id, db)


@router.get("/employee/me")
async def my_task_stats(
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    """Per-employee task summary across all meetings."""
    return await employee_controller.get_employee_task_summary(current_employee.id, db)
