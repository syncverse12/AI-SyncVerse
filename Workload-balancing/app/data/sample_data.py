"""
sample_data.py
--------------
Pre-built scenarios used by the /simulate endpoint and tests.
Each scenario describes a different team state to exercise all code paths.
"""

from __future__ import annotations
from typing import Dict, Any

SAMPLE_SCENARIOS: Dict[str, Any] = {

    # -----------------------------------------------------------------------
    # Balanced — healthy team, no action required
    # -----------------------------------------------------------------------
    "balanced": {
        "employees": [
            {
                "id": 1, "name": "Ahmed",
                "active_tasks": 4, "delayed_tasks": 0,
                "availability_score": 55,
                "task_complexity_distribution": {"low": 2, "medium": 2, "high": 0, "critical": 0},
                "past_success_rate": 0.90,
                "skills": ["backend", "python"],
            },
            {
                "id": 2, "name": "Sara",
                "active_tasks": 3, "delayed_tasks": 1,
                "availability_score": 60,
                "task_complexity_distribution": {"low": 1, "medium": 2, "high": 0, "critical": 0},
                "past_success_rate": 0.88,
                "skills": ["frontend", "react"],
            },
            {
                "id": 3, "name": "Omar",
                "active_tasks": 4, "delayed_tasks": 0,
                "availability_score": 50,
                "task_complexity_distribution": {"low": 1, "medium": 3, "high": 0, "critical": 0},
                "past_success_rate": 0.92,
                "skills": ["devops", "docker"],
            },
        ],
        "tasks": [],
    },

    # -----------------------------------------------------------------------
    # Overloaded — one clear overload, one available receiver
    # -----------------------------------------------------------------------
    "overloaded": {
        "employees": [
            {
                "id": 1, "name": "Ahmed",
                "active_tasks": 10, "delayed_tasks": 4,
                "availability_score": 10,
                "task_complexity_distribution": {"low": 1, "medium": 3, "high": 4, "critical": 2},
                "past_success_rate": 0.65,
                "skills": ["backend", "python", "ml"],
            },
            {
                "id": 2, "name": "Sara",
                "active_tasks": 2, "delayed_tasks": 0,
                "availability_score": 80,
                "task_complexity_distribution": {"low": 2, "medium": 0, "high": 0, "critical": 0},
                "past_success_rate": 0.93,
                "skills": ["backend", "python"],
            },
            {
                "id": 3, "name": "Lena",
                "active_tasks": 1, "delayed_tasks": 0,
                "availability_score": 90,
                "task_complexity_distribution": {"low": 1, "medium": 0, "high": 0, "critical": 0},
                "past_success_rate": 0.95,
                "skills": ["backend", "java", "spring"],
            },
        ],
        "tasks": [
            {
                "id": 10, "title": "Refactor auth module", "complexity": "medium",
                "priority": 4, "assigned_to": 1, "is_delayed": False, "estimated_hours": 6,
            },
            {
                "id": 11, "title": "Optimise DB queries", "complexity": "high",
                "priority": 7, "assigned_to": 1, "is_delayed": True, "estimated_hours": 8,
            },
            {
                "id": 12, "title": "Write unit tests", "complexity": "low",
                "priority": 3, "assigned_to": 1, "is_delayed": False, "estimated_hours": 3,
            },
            {
                "id": 13, "title": "Deploy to staging", "complexity": "medium",
                "priority": 5, "assigned_to": 1, "is_delayed": False, "estimated_hours": 2,
            },
        ],
    },

    # -----------------------------------------------------------------------
    # Critical — multiple overloaded, no available receivers
    # -----------------------------------------------------------------------
    "critical": {
        "employees": [
            {
                "id": 1, "name": "Ahmed",
                "active_tasks": 12, "delayed_tasks": 5,
                "availability_score": 5,
                "task_complexity_distribution": {"low": 0, "medium": 2, "high": 5, "critical": 5},
                "past_success_rate": 0.58,
                "skills": ["backend"],
            },
            {
                "id": 2, "name": "Sara",
                "active_tasks": 11, "delayed_tasks": 4,
                "availability_score": 8,
                "task_complexity_distribution": {"low": 1, "medium": 2, "high": 5, "critical": 3},
                "past_success_rate": 0.61,
                "skills": ["frontend"],
            },
            {
                "id": 3, "name": "Omar",
                "active_tasks": 9, "delayed_tasks": 3,
                "availability_score": 15,
                "task_complexity_distribution": {"low": 0, "medium": 3, "high": 4, "critical": 2},
                "past_success_rate": 0.70,
                "skills": ["devops"],
            },
        ],
        "tasks": [
            {
                "id": 20, "title": "Critical security patch", "complexity": "critical",
                "priority": 10, "assigned_to": 1, "is_delayed": True, "estimated_hours": 12,
            },
            {
                "id": 21, "title": "Performance regression fix", "complexity": "high",
                "priority": 9, "assigned_to": 2, "is_delayed": True, "estimated_hours": 8,
            },
            {
                "id": 22, "title": "Update API docs", "complexity": "low",
                "priority": 2, "assigned_to": 1, "is_delayed": False, "estimated_hours": 2,
            },
        ],
    },

    # -----------------------------------------------------------------------
    # Mixed — realistic heterogeneous team
    # -----------------------------------------------------------------------
    "mixed": {
        "employees": [
            {
                "id": 1, "name": "Ahmed",
                "active_tasks": 8, "delayed_tasks": 3,
                "availability_score": 20,
                "task_complexity_distribution": {"low": 1, "medium": 3, "high": 3, "critical": 1},
                "past_success_rate": 0.72,
                "skills": ["backend", "python"],
            },
            {
                "id": 2, "name": "Sara",
                "active_tasks": 5, "delayed_tasks": 1,
                "availability_score": 45,
                "task_complexity_distribution": {"low": 2, "medium": 2, "high": 1, "critical": 0},
                "past_success_rate": 0.89,
                "skills": ["frontend", "react", "typescript"],
            },
            {
                "id": 3, "name": "Omar",
                "active_tasks": 2, "delayed_tasks": 0,
                "availability_score": 75,
                "task_complexity_distribution": {"low": 2, "medium": 0, "high": 0, "critical": 0},
                "past_success_rate": 0.91,
                "skills": ["devops", "kubernetes"],
            },
            {
                "id": 4, "name": "Lena",
                "active_tasks": 6, "delayed_tasks": 2,
                "availability_score": 30,
                "task_complexity_distribution": {"low": 0, "medium": 4, "high": 2, "critical": 0},
                "past_success_rate": 0.84,
                "skills": ["ml", "python", "data"],
            },
            {
                "id": 5, "name": "Karim",
                "active_tasks": 1, "delayed_tasks": 0,
                "availability_score": 85,
                "task_complexity_distribution": {"low": 1, "medium": 0, "high": 0, "critical": 0},
                "past_success_rate": 0.96,
                "skills": ["backend", "java", "spring"],
            },
        ],
        "tasks": [
            {
                "id": 30, "title": "Implement OAuth2 flow", "complexity": "high",
                "priority": 8, "assigned_to": 1, "is_delayed": True, "estimated_hours": 10,
            },
            {
                "id": 31, "title": "Dashboard component redesign", "complexity": "medium",
                "priority": 6, "assigned_to": 2, "is_delayed": False, "estimated_hours": 5,
            },
            {
                "id": 32, "title": "Set up CI/CD pipeline", "complexity": "medium",
                "priority": 7, "assigned_to": 3, "is_delayed": False, "estimated_hours": 4,
            },
            {
                "id": 33, "title": "Train recommendation model", "complexity": "critical",
                "priority": 9, "assigned_to": 4, "is_delayed": True, "estimated_hours": 20,
            },
            {
                "id": 34, "title": "Write integration tests", "complexity": "low",
                "priority": 3, "assigned_to": 1, "is_delayed": False, "estimated_hours": 3,
            },
            {
                "id": 35, "title": "Code review backlog", "complexity": "low",
                "priority": 2, "assigned_to": 1, "is_delayed": False, "estimated_hours": 2,
            },
        ],
    },
}
