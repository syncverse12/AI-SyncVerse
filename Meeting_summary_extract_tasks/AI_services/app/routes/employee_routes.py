from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from AI_services.app.database.session import get_db
from AI_services.app.models.models import Employee, Task, MeetingSummary, Meeting, TaskStatus
from AI_services.app.schemas.schemas import TaskOut, SummaryOut, TaskUpdateIn
from AI_services.app.utils.auth import get_current_employee

router = APIRouter(prefix="/employee", tags=["Employee Dashboard"])


@router.get("/{employee_id}/tasks", response_model=list[TaskOut])
async def get_employee_tasks(
    employee_id: str,
    status: str = Query(default=None),
    meeting_id: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    """
    Get all tasks assigned to a specific employee.
    Only the employee themselves or an admin can view their tasks.
    """
    if current_employee.id != employee_id:
        raise HTTPException(status_code=403, detail="Access denied")

    query = select(Task).where(Task.assignee_id == employee_id)

    if status:
        query = query.where(Task.status == status.upper())
    if meeting_id:
        query = query.where(Task.meeting_id == meeting_id)

    query = query.order_by(Task.created_at.desc())
    result = await db.execute(query)
    tasks = result.scalars().all()
    return tasks


@router.get("/me/tasks", response_model=list[TaskOut])
async def get_my_tasks(
    status: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    """Get current employee's own tasks across all meetings."""
    query = select(Task).where(Task.assignee_id == current_employee.id)
    if status:
        query = query.where(Task.status == status.upper())
    query = query.order_by(Task.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/me/tasks/{task_id}", response_model=TaskOut)
async def update_task_status(
    task_id: str,
    body: TaskUpdateIn,
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    """Employee can update status/priority of their own tasks."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.assignee_id != current_employee.id:
        raise HTTPException(status_code=403, detail="Not your task")

    if body.status:
        task.status = body.status.upper()
    if body.priority:
        task.priority = body.priority.upper()
    if body.deadline is not None:
        task.deadline = body.deadline
    if body.description is not None:
        task.description = body.description

    await db.commit()
    await db.refresh(task)
    return task


@router.get("/me/meetings")
async def get_my_meetings(
    db: AsyncSession = Depends(get_db),
    current_employee: Employee = Depends(get_current_employee),
):
    """Get all meetings the current employee attended."""
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.attendees))
        .where(Meeting.attendees.any(Employee.id == current_employee.id))
        .order_by(Meeting.created_at.desc())
        .limit(30)
    )
    meetings = result.scalars().all()
    return [
        {
            "id": m.id,
            "title": m.title,
            "status": m.status,
            "started_at": m.started_at,
            "ended_at": m.ended_at,
        }
        for m in meetings
    ]
