"""
planner — AI Planning Module
============================

Public API
----------
from planner import (
    ProjectPlanner,
    Task, Resource, Sprint, ProjectPlan,
    ReplanningEvent, EventType,
    TaskStatus, TaskPriority,
)

Quick start
-----------
from datetime import date, timedelta
from planner import ProjectPlanner, Task, Resource, TaskPriority

resources = [
    Resource(name="Alice", skills=["backend", "python"]),
    Resource(name="Bob",   skills=["frontend", "react"]),
]

tasks = [
    Task(name="Design system architecture",  priority=TaskPriority.HIGH,
         required_skills=["backend"]),
    Task(name="Implement REST API",          priority=TaskPriority.HIGH,
         required_skills=["backend", "python"],
         dependencies=["<design-task-id>"]),
    Task(name="Build frontend dashboard",    priority=TaskPriority.MEDIUM,
         required_skills=["frontend", "react"],
         dependencies=["<api-task-id>"]),
]

planner = ProjectPlanner(
    project_name  = "My Project",
    deadline      = date.today() + timedelta(days=60),
    tasks         = tasks,
    resources     = resources,
)

plan = planner.build_initial_plan()
print(plan.to_dict())
"""

from .models import (
    EventType,
    ProjectPlan,
    ReplanningEvent,
    Resource,
    Sprint,
    Task,
    TaskPriority,
    TaskStatus,
)
from .dependency_graph import DependencyGraph, CPMNode
from .scheduler import SchedulingEngine
from .sprint_generator import SprintGenerator
from .replanning_engine import ReplanningEngine
from .planner import ProjectPlanner
from .utils import (
    estimate_task_duration,
    fill_missing_estimates,
    add_working_days,
    working_days_between,
    hours_to_working_days,
)

__all__ = [
    # Core planner
    "ProjectPlanner",
    # Models
    "Task",
    "Resource",
    "Sprint",
    "ProjectPlan",
    "ReplanningEvent",
    "EventType",
    "TaskStatus",
    "TaskPriority",
    # Sub-components (for advanced / direct use)
    "DependencyGraph",
    "CPMNode",
    "SchedulingEngine",
    "SprintGenerator",
    "ReplanningEngine",
    # Utilities
    "estimate_task_duration",
    "fill_missing_estimates",
    "add_working_days",
    "working_days_between",
    "hours_to_working_days",
]

__version__ = "1.0.0"
