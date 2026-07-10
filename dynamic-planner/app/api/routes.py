"""
app/api/routes.py
-----------------
All HTTP route handlers.

Route map
─────────────────────────────────────────────────────────
GET    /health                       Liveness probe
GET    /                             Service info
POST   /plan                         Create a new AI project plan
GET    /plan/{project_id}            Retrieve an existing plan
GET    /plan/{project_id}/summary    Lightweight plan summary
POST   /plan/{project_id}/replan     Apply a change event
DELETE /plan/{project_id}            Delete a project
GET    /plans                        List all projects
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.core.planner import create_plan, delete_plan, get_plan, list_projects, replan
from app.models.schemas import (
    ErrorResponse,
    HealthResponse,
    PlanResponse,
    ProjectRequest,
    ReplanEventRequest,
    ReplanResponse,
    SummaryResponse,
)
from app.utils.version import VERSION

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── System ────────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
)
async def health() -> HealthResponse:
    """Liveness probe — returns 200 when the service is ready."""
    return HealthResponse(status="ok", version=VERSION, timestamp=_now())


@router.get("/", include_in_schema=False)
async def root() -> Dict:
    return {
        "service": "AI Dynamic Project Planner",
        "version": VERSION,
        "status":  "running",
        "docs":    "/docs",
        "health":  "/health",
    }


# ── Planning ──────────────────────────────────────────────────────────────────

@router.post(
    "/plan",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new AI project plan",
    tags=["Planning"],
    responses={
        400: {"description": "Planning error (e.g. dependency cycle)"},
        422: {"description": "Validation error"},
    },
)
async def create_plan_endpoint(request: ProjectRequest) -> PlanResponse:
    """
    Submit a project (tasks + resources + deadline) and receive a fully
    scheduled, sprint-organised, resource-levelled AI plan.

    The engine will:
    - **Estimate** missing task durations via keyword + priority heuristic
    - **Validate** the dependency graph — rejects cycles → HTTP 400
    - **Run CPM** — forward/backward pass, identify critical path + float
    - **Assign** tasks to resources — skill matching + capacity levelling
    - **Group** tasks into time-boxed sprints with load balancing
    - **Warn** if the completion date exceeds the hard deadline
    """
    try:
        return create_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/plan/{project_id}",
    response_model=PlanResponse,
    summary="Retrieve an existing plan",
    tags=["Planning"],
    responses={404: {"description": "Project not found"}},
)
async def get_plan_endpoint(project_id: str) -> PlanResponse:
    """Return the current full plan for a project."""
    try:
        return get_plan(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/plan/{project_id}/summary",
    response_model=SummaryResponse,
    summary="Lightweight plan summary",
    tags=["Planning"],
    responses={404: {"description": "Project not found"}},
)
async def get_summary_endpoint(project_id: str) -> SummaryResponse:
    """
    Return on-time flag, completion date, task/sprint counts, and warnings
    — without the full task/sprint/resource lists.
    """
    try:
        return get_plan(project_id, summary_only=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/plan/{project_id}/replan",
    response_model=ReplanResponse,
    summary="Apply a replanning event",
    tags=["Planning"],
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Invalid event payload"},
    },
)
async def replan_endpoint(project_id: str, request: ReplanEventRequest) -> ReplanResponse:
    """
    Apply a real-world change event to an existing plan and receive the
    updated schedule.

    | event_type | new_value | Requires |
    |---|---|---|
    | `task_completed_early` | float (actual hours) | task_id |
    | `task_completed_late`  | float (actual hours) | task_id |
    | `task_added`           | TaskIn dict          | — |
    | `task_removed`         | —                    | task_id |
    | `resource_unavailable` | —                    | resource_id |
    | `resource_capacity_changed` | float 0.0–1.0  | resource_id |
    | `dependency_changed`   | list of task IDs     | task_id |

    Only the affected subgraph is rescheduled — minimal disruption.
    A warning is added if the updated completion date exceeds the deadline.
    """
    try:
        return replan(project_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/plan/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a project plan",
    tags=["Planning"],
    responses={404: {"description": "Project not found"}},
)
async def delete_plan_endpoint(project_id: str) -> None:
    """Remove a project and its plan from the store."""
    if not delete_plan(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")


@router.get(
    "/plans",
    summary="List all projects",
    tags=["Planning"],
)
async def list_plans_endpoint() -> List[Dict]:
    """Return lightweight summaries for all projects in the store."""
    return list_projects()
