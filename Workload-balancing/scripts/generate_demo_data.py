"""
One-off generator for app/data/demo/*.json fixtures. Not imported at
runtime — DemoDataProvider reads the generated JSON files directly.
Run: python scripts/generate_demo_data.py
"""
import json
import os
from datetime import datetime, timedelta

NOW = datetime(2026, 7, 11, 12, 0, 0)
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "data", "demo")


def iso(dt):
    return dt.isoformat()


def emp(id_, first, last, seniority, dept, skills, availability, role="engineer"):
    return {
        "id": id_, "first_name": first, "last_name": last,
        "seniority_level": seniority, "department": dept,
        "skills_raw": json.dumps(skills), "availability_status": availability,
        "role": role,
    }


def task(id_, title, status, priority, assignee, project, category, category_name,
         due_offset_days=None, started_offset_days=None, completed_offset_days=None,
         depends_on=None, comments=0, desc=""):
    d = {
        "id": id_, "title": title, "description": desc, "status": status,
        "priority": priority, "assigned_to_user_id": assignee,
        "project_id": project, "category_id": category, "category_name": category_name,
        "workspace_id": "ws-1", "depends_on_task_ids": depends_on or [],
        "comment_count": comments,
    }
    if due_offset_days is not None:
        d["due_date"] = iso(NOW + timedelta(days=due_offset_days))
    if started_offset_days is not None:
        d["task_started_at"] = iso(NOW - timedelta(days=started_offset_days))
    if completed_offset_days is not None:
        d["task_completed_at"] = iso(NOW - timedelta(days=completed_offset_days))
    d["created_at"] = iso(NOW - timedelta(days=(started_offset_days or 5) + 2))
    return d


def timelog(id_, task_id, user_id, days_ago, minutes):
    start = NOW - timedelta(days=days_ago, minutes=minutes)
    end = start + timedelta(minutes=minutes)
    return {
        "id": id_, "task_id": task_id, "user_id": user_id,
        "start_time": iso(start), "end_time": iso(end), "duration_minutes": minutes,
    }


def snapshot(scope_type, scope_id, scope_name, employees, tasks, time_logs):
    return {
        "scope_type": scope_type, "scope_id": scope_id, "scope_name": scope_name,
        "employees": employees, "tasks": tasks, "time_logs": time_logs,
    }


SCENARIOS = {}

# ---------------------------------------------------------------------
# normal_project — healthy, balanced team
# ---------------------------------------------------------------------
employees = [
    emp("u1", "Ahmed", "Nasser", 2, 1, ["backend", "python"], "Available"),
    emp("u2", "Sara", "Ali", 2, 2, ["frontend", "react"], "Available"),
    emp("u3", "Omar", "Khaled", 3, 3, ["devops", "docker"], "Busy"),
]
tasks = [
    task("t1", "Implement login API", "in_progress", 5, "u1", "p1", "c1", "Backend", due_offset_days=5, started_offset_days=2, comments=2),
    task("t2", "Fix pagination bug", "todo", 3, "u1", "p1", "c1", "Backend", due_offset_days=7, comments=0),
    task("t3", "Build dashboard UI", "in_progress", 6, "u2", "p1", "c2", "Frontend", due_offset_days=4, started_offset_days=1, comments=3),
    task("t4", "Set up CI pipeline", "todo", 4, "u3", "p1", "c3", "DevOps", due_offset_days=6, comments=1),
    task("t5", "Write onboarding docs", "done", 2, "u1", "p1", "c1", "Backend", completed_offset_days=1, comments=0),
]
logs = [
    timelog("l1", "t1", "u1", 1, 240), timelog("l2", "t3", "u2", 1, 300),
    timelog("l3", "t4", "u3", 2, 180),
]
SCENARIOS["normal_project"] = snapshot("project", "p1", "Normal Project", employees, tasks, logs)

# ---------------------------------------------------------------------
# overloaded_team — one person drowning, others fine
# ---------------------------------------------------------------------
employees = [
    emp("u1", "Ahmed", "Nasser", 3, 1, ["backend", "python", "ml"], "Busy"),
    emp("u2", "Sara", "Ali", 2, 1, ["backend", "python"], "Available"),
    emp("u3", "Lena", "Fahmy", 2, 1, ["backend", "java"], "Available"),
]
tasks = [
    task("t1", "Refactor auth module", "in_progress", 4, "u1", "p2", "c1", "Backend", due_offset_days=2, started_offset_days=5, comments=4),
    task("t2", "Optimise DB queries", "in_progress", 7, "u1", "p2", "c1", "Backend", due_offset_days=-1, started_offset_days=8, comments=6),
    task("t3", "Write unit tests", "todo", 3, "u1", "p2", "c1", "Backend", due_offset_days=3),
    task("t4", "Deploy to staging", "todo", 5, "u1", "p2", "c1", "Backend", due_offset_days=1),
    task("t5", "Critical security patch", "in_review", 9, "u1", "p2", "c1", "Backend", due_offset_days=-2, started_offset_days=6, comments=5),
    task("t6", "Update landing page copy", "todo", 2, "u2", "p2", "c2", "Content", due_offset_days=10),
    task("t7", "Spike: caching layer", "todo", 3, "u3", "p2", "c1", "Backend", due_offset_days=12),
]
logs = [timelog("l1", "t1", "u1", 1, 480), timelog("l2", "t2", "u1", 2, 420),
        timelog("l3", "t5", "u1", 1, 360), timelog("l4", "t6", "u2", 3, 90)]
SCENARIOS["overloaded_team"] = snapshot("project", "p2", "Overloaded Team", employees, tasks, logs)

# ---------------------------------------------------------------------
# underutilized_team — plenty of slack
# ---------------------------------------------------------------------
employees = [
    emp("u1", "Karim", "Adel", 1, 2, ["frontend"], "Available"),
    emp("u2", "Mona", "Said", 2, 2, ["frontend", "design"], "Available"),
]
tasks = [
    task("t1", "Update footer links", "todo", 2, "u1", "p3", "c2", "Frontend", due_offset_days=14),
    task("t2", "Review design tokens", "done", 3, "u2", "p3", "c2", "Frontend", completed_offset_days=3),
]
logs = [timelog("l1", "t1", "u1", 5, 60)]
SCENARIOS["underutilized_team"] = snapshot("project", "p3", "Underutilized Team", employees, tasks, logs)

# ---------------------------------------------------------------------
# delayed_project — many overdue tasks, blocked dependencies
# ---------------------------------------------------------------------
employees = [
    emp("u1", "Ahmed", "Nasser", 3, 1, ["backend"], "Busy"),
    emp("u2", "Sara", "Ali", 2, 2, ["frontend"], "Busy"),
    emp("u3", "Omar", "Khaled", 2, 3, ["devops"], "Available"),
]
tasks = [
    task("t1", "Migrate to new API gateway", "in_progress", 8, "u1", "p4", "c1", "Backend", due_offset_days=-5, started_offset_days=15, comments=8),
    task("t2", "Integration tests for gateway", "todo", 6, "u1", "p4", "c1", "Backend", due_offset_days=-2, depends_on=["t1"]),
    task("t3", "Update client SDK", "todo", 5, "u2", "p4", "c2", "Frontend", due_offset_days=-3, depends_on=["t1"]),
    task("t4", "Deploy gateway to prod", "todo", 9, "u3", "p4", "c3", "DevOps", due_offset_days=-1, depends_on=["t1", "t2"]),
]
logs = [timelog("l1", "t1", "u1", 2, 300)]
SCENARIOS["delayed_project"] = snapshot("project", "p4", "Delayed Project", employees, tasks, logs)

# ---------------------------------------------------------------------
# high_priority_project — everything urgent, tight team
# ---------------------------------------------------------------------
employees = [
    emp("u1", "Ahmed", "Nasser", 3, 1, ["backend"], "Busy"),
    emp("u2", "Sara", "Ali", 3, 1, ["backend", "python"], "Busy"),
]
tasks = [
    task("t1", "Launch-blocking payment bug", "in_progress", 10, "u1", "p5", "c1", "Backend", due_offset_days=1, started_offset_days=1, comments=5),
    task("t2", "Fraud detection rule update", "in_progress", 9, "u2", "p5", "c1", "Backend", due_offset_days=1, started_offset_days=1, comments=3),
    task("t3", "Rollback plan documentation", "todo", 8, "u1", "p5", "c1", "Backend", due_offset_days=2),
]
logs = [timelog("l1", "t1", "u1", 1, 360), timelog("l2", "t2", "u2", 1, 300)]
SCENARIOS["high_priority_project"] = snapshot("project", "p5", "High Priority Project", employees, tasks, logs)

# ---------------------------------------------------------------------
# critical_project — multiple overloaded, no receivers, cascading risk
# ---------------------------------------------------------------------
employees = [
    emp("u1", "Ahmed", "Nasser", 3, 1, ["backend"], "Busy"),
    emp("u2", "Sara", "Ali", 3, 1, ["frontend"], "Busy"),
    emp("u3", "Omar", "Khaled", 2, 3, ["devops"], "Busy"),
]
tasks = [
    task("t1", "Critical security patch", "in_review", 10, "u1", "p6", "c1", "Backend", due_offset_days=-3, started_offset_days=10, comments=9),
    task("t2", "Data corruption hotfix", "in_progress", 10, "u1", "p6", "c1", "Backend", due_offset_days=-1, started_offset_days=6, comments=7),
    task("t3", "Perf regression on checkout", "in_progress", 9, "u2", "p6", "c2", "Frontend", due_offset_days=-2, started_offset_days=7, comments=6),
    task("t4", "Prod incident postmortem", "todo", 7, "u2", "p6", "c2", "Frontend", due_offset_days=-1),
    task("t5", "Restore backups", "in_progress", 10, "u3", "p6", "c3", "DevOps", due_offset_days=-4, started_offset_days=9, comments=8),
    task("t6", "Update API docs", "todo", 2, "u1", "p6", "c1", "Backend", due_offset_days=5),
]
logs = [timelog("l1", "t1", "u1", 1, 420), timelog("l2", "t2", "u1", 1, 360),
        timelog("l3", "t3", "u2", 1, 400), timelog("l4", "t5", "u3", 1, 450)]
SCENARIOS["critical_project"] = snapshot("project", "p6", "Critical Project", employees, tasks, logs)

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, data in SCENARIOS.items():
        path = os.path.join(OUT_DIR, f"{name}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"wrote {path}")
