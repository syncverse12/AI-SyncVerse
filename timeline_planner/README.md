# 🧠 AI Dynamic Project Planner

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/Tests-25%2F25%20passing-brightgreen)
![Lines](https://img.shields.io/badge/Source-2%2C265%20lines-informational)
![Status](https://img.shields.io/badge/Status-Production--Ready-success)

**A rule-based AI scheduling engine that builds, optimises, and dynamically replans project timelines — no ML training required.**

[Features](#-features) · [Architecture](#-architecture) · [Quickstart](#-quickstart) · [API Reference](#-api-reference) · [Algorithms](#-algorithms) · [Roadmap](#-roadmap)

</div>

---

## Overview

Most project management tools are static: you build a plan once and manually patch it every time reality diverges. **AI Dynamic Project Planner** takes a different approach — it treats the schedule as a *living artefact* that automatically heals itself when things change.

Given a list of tasks, their dependencies, a deadline, and a team, the engine will:

- **Estimate** missing task durations using a keyword-driven heuristic
- **Schedule** every task onto a real calendar respecting dependencies, resource capacity, and skill requirements
- **Identify** the critical path so you always know which tasks cannot slip
- **Group** work into sprint-sized chunks with load balancing
- **Replan** intelligently the moment something unexpected happens — without rebuilding from scratch

The module is pure Python with zero external runtime dependencies. All outputs are plain dataclasses with a `.to_dict()` method, making them trivially serialisable by FastAPI, Django, or any other framework.

---

## ✨ Features

| Capability | Detail |
|---|---|
| **AI Duration Estimation** | Keyword + priority + skill-complexity heuristic fills gaps when task hours are unknown |
| **DAG Dependency Modelling** | Full directed acyclic graph with cycle detection and transitive ancestor/descendant queries |
| **Critical Path Method (CPM)** | Forward + backward pass, total float, free float, and critical path extraction |
| **Resource Levelling** | Capacity-aware assignment with skill matching; no resource is ever double-booked |
| **Sprint Generation** | Heuristic sprint grouping with configurable length, load cap, and critical-task protection |
| **Event-Driven Replanning** | Seven discrete event types trigger targeted, minimal-disruption rescheduling |
| **Deadline Alerting** | Automatic warnings when the plan's completion date drifts past the hard deadline |
| **FastAPI-Ready** | All outputs are plain dataclasses with `.to_dict()` — plug straight into any endpoint |

---

## 🗂 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ProjectPlanner                           │
│  (facade — single entry point for all external callers)         │
│                                                                 │
│   build_initial_plan()   recalculate_plan()   generate_sprints()│
└──────────┬──────────────────────┬──────────────────────────────┘
           │                      │
    ┌──────▼───────┐    ┌─────────▼──────────┐
    │ Dependency   │    │  ReplanningEngine  │
    │   Graph      │    │                    │
    │  (DAG+CPM)   │    │  event dispatch    │
    └──────┬───────┘    │  impact analysis   │
           │            │  targeted reschedule│
    ┌──────▼───────┐    └─────────┬──────────┘
    │ Scheduling   │              │
    │   Engine     │◄─────────────┘
    │              │
    │ resource     │
    │ levelling    │
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │    Sprint    │
    │  Generator   │
    │              │
    │ heuristic    │
    │ grouping     │
    └──────────────┘
```

### Data flow

```
Input (tasks + resources + deadline)
         │
         ▼
   fill_missing_estimates()          ← utils.py
         │
         ▼
   DependencyGraph.build()           ← dependency_graph.py
   DependencyGraph.validate_dag()
         │
         ▼
   DependencyGraph.compute_cpm()     ← ES / EF / LS / LF / float
         │
         ▼
   SchedulingEngine.schedule()       ← calendar dates + resource assignment
         │
         ▼
   SprintGenerator.generate_sprints()← sprint groups + load balancing
         │
         ▼
   ProjectPlan                       ← models.py — fully serialisable
```

---

## 📁 Folder Structure

```
planner/
├── __init__.py             # Public API surface — import everything from here
├── models.py               # Task, Resource, Sprint, ProjectPlan, ReplanningEvent
├── dependency_graph.py     # DAG construction, cycle detection, CPM
├── scheduler.py            # ResourceLoadTracker, SchedulingEngine
├── sprint_generator.py     # SprintGenerator (heuristic grouping)
├── replanning_engine.py    # ReplanningEngine — all 7 event handlers
├── planner.py              # ProjectPlanner facade
└── utils.py                # Duration estimator, calendar helpers

tests/
└── test_planner.py         # 25 integration tests (no external dependencies)
```

---

## 🚀 Quickstart

### Requirements

- Python 3.9 or above
- No third-party packages required

### Install

```bash
git clone https://github.com/your-org/ai-project-planner.git
cd ai-project-planner
# no pip install needed — stdlib only
```

### Run the tests

```bash
python tests/test_planner.py
```

```
============================================================
 AI Planning Module — Test Suite
============================================================

1. Duration Estimation          ✓ ✓ ✓
2. Dependency Graph & CPM       ✓ ✓ ✓ ✓ ✓
3. Full Initial Plan            ✓ ✓ ✓ ✓ ✓ ✓
4. Replanning Engine            ✓ ✓ ✓ ✓ ✓ ✓ ✓ ✓
5. Edge Cases                   ✓ ✓ ✓

Results: 25/25 tests passed
```

---

## 💡 Example Usage

### 1 — Build an initial plan

```python
from datetime import date, timedelta
from planner import (
    ProjectPlanner, Task, Resource,
    TaskPriority, TaskStatus,
)

# Define the team
resources = [
    Resource(name="Alice", capacity=1.0, skills=["backend", "python"]),
    Resource(name="Bob",   capacity=0.8, skills=["frontend", "react"]),
    Resource(name="Carol", capacity=1.0, skills=["devops", "docker"]),
]

# Define tasks (estimated_hours is optional — the AI fills it in)
t1 = Task(name="Design system architecture",
          priority=TaskPriority.HIGH, required_skills=["backend"])
t2 = Task(name="Set up CI/CD pipeline",
          priority=TaskPriority.HIGH, required_skills=["devops"])
t3 = Task(name="Implement REST API",
          priority=TaskPriority.HIGH, required_skills=["backend", "python"],
          dependencies=[t1.id])
t4 = Task(name="Build frontend dashboard",
          priority=TaskPriority.MEDIUM, required_skills=["frontend", "react"],
          dependencies=[t3.id])
t5 = Task(name="Deploy to production",
          priority=TaskPriority.CRITICAL, required_skills=["devops"],
          dependencies=[t4.id, t2.id])

planner = ProjectPlanner(
    project_name   = "My SaaS MVP",
    deadline       = date.today() + timedelta(days=60),
    tasks          = [t1, t2, t3, t4, t5],
    resources      = resources,
    project_start  = date.today(),
    sprint_length_days = 14,
)

plan = planner.build_initial_plan()

print(plan.is_on_time)          # True / False
print(plan.completion_date)     # e.g. 2025-08-12
print(plan.critical_path)       # [t1.id, t3.id, t4.id, t5.id]

# Fully serialisable — plug straight into FastAPI
import json
print(json.dumps(plan.to_dict(), indent=2))
```

### 2 — React to a real-world event

```python
from planner import ReplanningEvent, EventType

# A task took twice as long as expected
event = ReplanningEvent(
    event_type = EventType.TASK_COMPLETED_LATE,
    task_id    = t3.id,
    new_value  = 80.0,   # actual hours (vs 40.0 estimated)
)

updated_plan = planner.recalculate_plan(event)
print(updated_plan.warnings)   # deadline risk messages if any
```

```python
# A team member goes on sick leave
event = ReplanningEvent(
    event_type  = EventType.RESOURCE_UNAVAILABLE,
    resource_id = resources[0].id,   # Alice
)
updated_plan = planner.recalculate_plan(event)
# Alice's tasks are automatically reassigned to available resources
```

```python
# Add a new task mid-project
security_audit = Task(
    name            = "Security penetration test",
    priority        = TaskPriority.HIGH,
    required_skills = ["backend"],
    estimated_hours = 16.0,
    dependencies    = [t3.id],
)

event = ReplanningEvent(
    event_type = EventType.TASK_ADDED,
    new_value  = security_audit,
)
updated_plan = planner.recalculate_plan(event)
```

### 3 — FastAPI integration (3 lines of glue)

```python
from fastapi import FastAPI
from planner import ProjectPlanner, ReplanningEvent

app = FastAPI()
planner: ProjectPlanner = ...   # initialised at startup

@app.get("/plan")
def get_plan():
    return planner.current_plan.to_dict()

@app.post("/plan/replan")
def replan(event: dict):
    updated = planner.recalculate_plan(ReplanningEvent(**event))
    return updated.to_dict()
```

---

## 📐 Algorithms

### Dependency Graph (DAG)

All task relationships are modelled as a directed acyclic graph.

- **Construction** — each task's `dependencies` list creates a directed edge from predecessor → task
- **Cycle detection** — Kahn's BFS algorithm; raises `ValueError` before any scheduling begins
- **Topological sort** — Kahn's BFS with priority-rank tie-breaking (CRITICAL tasks surface first)
- **Transitive queries** — `all_ancestors()` and `all_descendants()` via BFS; used by the replanning engine to scope impact

### Critical Path Method (CPM)

The classic CPM two-pass algorithm runs on every (re)plan.

| Pass | Computes | Formula |
|---|---|---|
| **Forward** | Earliest Start (ES), Earliest Finish (EF) | `ES = max(EF of predecessors)` |
| **Backward** | Latest Start (LS), Latest Finish (LF) | `LF = min(LS of successors)` |
| **Float** | Total float, Free float | `TF = LS − ES` |
| **Critical** | Is the task critical? | `TF == 0` |

The critical path is then extracted as the longest path through the zero-float subgraph using dynamic programming.

### Resource Levelling

`ResourceLoadTracker` maintains a per-resource, per-day committed-hours register.

**Scheduling a task:**

1. Find the earliest calendar date all predecessors have finished.
2. Score every resource: `score = (skill_overlap × 2) − load_ratio_penalty`
3. Pick the highest-scoring resource that has capacity on that date.
4. Advance the task's start to the first date where capacity ≥ required daily hours.
5. Commit hours to the tracker so subsequent tasks see accurate availability.

**Result:** no resource is ever over-allocated; skill matching is a first-class concern.

### Heuristic Sprint Grouping

`SprintGenerator` maps scheduled tasks onto fixed-width sprint windows.

1. Sprint windows are built from `project_start` to `completion_date` at `sprint_length_days` intervals.
2. Tasks are sorted: critical-path tasks first, then by `start_date`, then by priority.
3. Each task is placed in the sprint that contains its `start_date`.
4. If placing a task would push sprint load above `max_load_ratio` (default 90 %), it is deferred — **unless** it is on the critical path, in which case it is force-placed with a warning.

### Event-Driven Replanning

`ReplanningEngine` processes seven event types:

| Event | Trigger | Impact scope |
|---|---|---|
| `TASK_COMPLETED_EARLY` | Actual hours < estimated | All downstream tasks (may pull forward) |
| `TASK_COMPLETED_LATE` | Actual hours > estimated | All downstream tasks (cascade delay) |
| `TASK_ADDED` | New task injected | New task + its descendants |
| `TASK_REMOVED` | Task deleted | Former dependents (now unblocked) |
| `RESOURCE_UNAVAILABLE` | Member goes offline | All their unfinished tasks |
| `RESOURCE_CAPACITY_CHANGED` | Capacity fraction updated | All tasks assigned to that resource |
| `DEPENDENCY_CHANGED` | Dependency list replaced | Affected task + its descendants |

**Minimising disruption:** only tasks inside the computed impact set have their dates reset; completed tasks and unaffected tasks are left untouched. A full CPM + resource-levelling pass then runs only over the affected subgraph before regenerating sprints.

---

## 🗃 API Reference

### `ProjectPlanner`

| Method | Signature | Returns |
|---|---|---|
| `build_initial_plan` | `() → ProjectPlan` | Full initial plan |
| `generate_sprints` | `(tasks?, resources?, critical_path?) → List[Sprint]` | Updated sprint list |
| `recalculate_plan` | `(event: ReplanningEvent) → ProjectPlan` | Updated plan |
| `update_dependencies` | `(task_id, new_deps) → ProjectPlan` | Updated plan |
| `allocate_resources` | `(tasks?, resources?) → List[Task]` | Tasks with assignments |
| `summary` | `() → dict` | Lightweight status dict |

### `ReplanningEvent` fields

| Field | Type | Description |
|---|---|---|
| `event_type` | `EventType` | One of the 7 event types |
| `task_id` | `str \| None` | Target task (when applicable) |
| `resource_id` | `str \| None` | Target resource (when applicable) |
| `new_value` | `Any` | Actual hours, new capacity, new Task, or new dep list |

### `ProjectPlan` fields

| Field | Type | Description |
|---|---|---|
| `tasks` | `List[Task]` | All tasks with scheduled dates and assignments |
| `sprints` | `List[Sprint]` | Ordered sprint structure |
| `resources` | `List[Resource]` | Resource roster with current capacity |
| `critical_path` | `List[str]` | Ordered task IDs on the critical path |
| `is_on_time` | `bool` | `completion_date <= deadline` |
| `warnings` | `List[str]` | Deadline risk and other non-fatal alerts |

---

## 🔮 Roadmap

### Near-term

- [ ] **Pydantic v2 models** — replace `@dataclass` with `BaseModel` for automatic FastAPI schema generation and request validation
- [ ] **Holiday calendars** — integrate `workalendar` or a custom calendar provider so country-specific public holidays are skipped
- [ ] **Partial-day resource allocation** — support tasks requiring less than a full working day (e.g. 2 h meetings)
- [ ] **Multi-project resource pooling** — allow a single resource roster to be shared across several concurrent projects with a global load view

### Medium-term

- [ ] **Gantt chart export** — output a Mermaid or SVG Gantt diagram directly from `ProjectPlan.to_gantt()`
- [ ] **Slack / MS Teams notifications** — emit event hooks when tasks are auto-rescheduled past a threshold
- [ ] **REST persistence layer** — optional SQLite / PostgreSQL adapter so plans survive server restarts
- [ ] **WebSocket live updates** — push replanning diffs to connected clients in real time

### Long-term

- [ ] **ML duration estimation** — replace the keyword heuristic with a lightweight regression model trained on historical task completion data
- [ ] **Monte Carlo schedule simulation** — run N probabilistic simulations to produce confidence intervals on the completion date
- [ ] **Multi-objective optimisation** — expose a pluggable optimiser interface (e.g. genetic algorithm) for cost vs. time vs. risk trade-off analysis
- [ ] **Team skills ontology** — integrate a skills graph so partial skill matches (e.g. "Python" → "backend") are reasoned about semantically

---

## 🤝 Contributing

1. Fork the repo and create a feature branch: `git checkout -b feat/my-feature`
2. Add tests for any new behaviour in `tests/test_planner.py`
3. Ensure `python tests/test_planner.py` exits with `Results: N/N tests passed`
4. Open a pull request with a clear description of the change

---

## 📄 License

MIT © 2025 — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built with pure Python · Zero runtime dependencies · Production-ready
</div>
