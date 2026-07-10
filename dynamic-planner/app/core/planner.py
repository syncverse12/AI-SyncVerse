"""
app/core/planner.py
--------------------
Adapter layer — translates Pydantic request objects into engine dataclasses,
calls the AI planning engine, and translates results back into Pydantic responses.

Also manages the in-memory project store:
    project_id (str) → ProjectPlanner instance

In production, swap _store for a Redis-backed adapter without touching any
other file.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Union

# ── AI engine ─────────────────────────────────────────────────────────────────
from planner import (
    EventType,
    ProjectPlanner,
    ReplanningEvent,
    Resource,
    Task,
    TaskPriority,
)

# ── Schemas ───────────────────────────────────────────────────────────────────
from app.models.schemas import (
    PlanResponse,
    ProjectRequest,
    ReplanEventRequest,
    ReplanResponse,
    ResourceIn,
    ResourceOut,
    SprintOut,
    SummaryResponse,
    TaskIn,
    TaskOut,
)
from planner.engine import get_logger

logger = get_logger("service.core")

# ── In-memory store ────────────────────────────────────────────────────────────
_store: Dict[str, ProjectPlanner] = {}


# ── Schema → dataclass converters ─────────────────────────────────────────────

def _to_resource(r: ResourceIn) -> Resource:
    kwargs: Dict[str, Any] = {
        "name":            r.name,
        "capacity":        r.capacity,
        "skills":          list(r.skills),
        "available_from":  r.available_from or date.today(),
        "available_until": r.available_until,
    }
    if r.id:
        kwargs["id"] = r.id
    return Resource(**kwargs)


def _to_task(t: Union[TaskIn, Dict]) -> Task:
    if isinstance(t, dict):
        t = TaskIn(**t)
    kwargs: Dict[str, Any] = {
        "name":            t.name,
        "description":     t.description,
        "estimated_hours": t.estimated_hours,
        "dependencies":    list(t.dependencies),
        "priority":        TaskPriority(t.priority),
        "required_skills": list(t.required_skills),
        "is_milestone":    t.is_milestone,
        "metadata":        dict(t.metadata),
    }
    if t.id:
        kwargs["id"] = t.id
    return Task(**kwargs)


def _resolve_new_value(event_type: str, raw: Any) -> Any:
    """Convert raw new_value to the type the engine expects per event_type."""
    if event_type in ("task_completed_early", "task_completed_late"):
        return float(raw) if raw is not None else None
    if event_type == "resource_capacity_changed":
        return float(raw) if raw is not None else None
    if event_type == "task_added":
        if isinstance(raw, dict):
            return _to_task(TaskIn(**raw))
        if isinstance(raw, TaskIn):
            return _to_task(raw)
        raise ValueError("task_added requires new_value to be a Task object (dict or TaskIn)")
    if event_type == "dependency_changed":
        if isinstance(raw, list):
            return [str(dep) for dep in raw]
        raise ValueError("dependency_changed requires new_value to be a list of task IDs")
    return None  # task_removed, resource_unavailable


# ── Plan → response converter ─────────────────────────────────────────────────

def _plan_to_response(project_id: str, plan, event_type: Optional[str] = None):
    d = plan.to_dict()
    tasks     = [TaskOut(**t) for t in d["tasks"]]
    sprints   = [SprintOut(**s) for s in d["sprints"]]
    resources = [
        ResourceOut(
            id=r["id"], name=r["name"], capacity=r["capacity"],
            skills=r["skills"], available_from=r["available_from"],
            available_until=r.get("available_until"),
        )
        for r in d["resources"]
    ]
    common = dict(
        project_id=project_id,
        project_name=d["project_name"],
        deadline=d["deadline"],
        created_at=d["created_at"],
        is_on_time=d["is_on_time"],
        completion_date=d.get("completion_date"),
        total_estimated_hours=d["total_estimated_hours"],
        critical_path=d["critical_path"],
        warnings=d["warnings"],
        tasks=tasks,
        sprints=sprints,
        resources=resources,
    )
    if event_type is not None:
        return ReplanResponse(event_type=event_type, **common)
    return PlanResponse(**common)


def _plan_to_summary(project_id: str, planner: ProjectPlanner) -> SummaryResponse:
    s = planner.summary()
    return SummaryResponse(
        project_id=project_id,
        project_name=s["project_name"],
        deadline=s["deadline"],
        is_on_time=s["is_on_time"],
        completion_date=s.get("completion_date"),
        total_tasks=s["total_tasks"],
        total_sprints=s["total_sprints"],
        total_resources=s["total_resources"],
        critical_path_length=s["critical_path_length"],
        warnings=s["warnings"],
    )


# ── Public service functions (called by route handlers) ───────────────────────

def create_plan(request: ProjectRequest) -> PlanResponse:
    """Build a new project plan and store it. Returns the full plan response."""
    project_id = str(uuid.uuid4())
    resources  = [_to_resource(r) for r in request.resources]
    tasks      = [_to_task(t)     for t in request.tasks]

    engine = ProjectPlanner(
        project_name       = request.project_name,
        deadline           = request.deadline,
        tasks              = tasks,
        resources          = resources,
        project_start      = request.project_start or date.today(),
        sprint_length_days = request.sprint_length_days,
        hours_per_day      = request.hours_per_day,
    )
    plan = engine.build_initial_plan()
    _store[project_id] = engine

    logger.info("Project '%s' created (id=%s, completion=%s, on_time=%s)",
                request.project_name, project_id, plan.completion_date, plan.is_on_time)
    return _plan_to_response(project_id, plan)


def get_plan(project_id: str, summary_only: bool = False):
    """Retrieve an existing plan by project_id."""
    engine = _store.get(project_id)
    if engine is None:
        raise KeyError(f"Project '{project_id}' not found.")
    if summary_only:
        return _plan_to_summary(project_id, engine)
    if engine.current_plan is None:
        raise RuntimeError("Plan has not been built yet.")
    return _plan_to_response(project_id, engine.current_plan)


def replan(project_id: str, request: ReplanEventRequest) -> ReplanResponse:
    """Apply a replanning event to an existing project."""
    engine = _store.get(project_id)
    if engine is None:
        raise KeyError(f"Project '{project_id}' not found.")

    resolved = _resolve_new_value(request.event_type, request.new_value)
    event = ReplanningEvent(
        event_type  = EventType(request.event_type),
        task_id     = request.task_id,
        resource_id = request.resource_id,
        new_value   = resolved,
    )
    updated_plan = engine.recalculate_plan(event)

    logger.info("Replanned '%s' (event=%s, completion=%s, on_time=%s)",
                project_id, request.event_type, updated_plan.completion_date,
                updated_plan.is_on_time)
    return _plan_to_response(project_id, updated_plan, request.event_type)


def delete_plan(project_id: str) -> bool:
    """Remove a project from the store. Returns True if it existed."""
    existed = project_id in _store
    _store.pop(project_id, None)
    return existed


def list_projects() -> List[Dict]:
    """Return lightweight summaries for all stored projects."""
    return [{"project_id": pid, **p.summary()} for pid, p in _store.items()]
