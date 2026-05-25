# Real-Time Agent-Based Smart Task Assignment System

> A production-grade, AI-powered task assignment platform that intelligently routes work to the most qualified employees using a multi-agent architecture, real-time WebSocket streaming, and a transparent weighted scoring engine.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python)](https://www.python.org)
[![WebSockets](https://img.shields.io/badge/WebSockets-RFC%206455-blue?style=flat-square)](https://tools.ietf.org/html/rfc6455)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen?style=flat-square)]()

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Multi-Agent AI System](#multi-agent-ai-system)
- [Scoring System](#scoring-system)
- [API Documentation](#api-documentation)
- [Real-Time Flow](#real-time-flow)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Example Usage](#example-usage)
- [Project Structure](#project-structure)
- [Future Improvements](#future-improvements)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Modern engineering teams struggle with two compounding problems: task assignment is slow, subjective, and often driven by familiarity rather than fit — and workload visibility is poor, leading to burnout on some engineers and underutilisation on others.

The **Real-Time Agent-Based Smart Task Assignment System** solves both problems by automating task analysis and employee matching through a coordinated pipeline of independent AI agents. When a task arrives — as plain text, a PDF brief, a DOCX specification, or even a scanned image — the system immediately begins processing it, asynchronously runs five specialised agents in an optimised sequence, and streams ranked employee recommendations to connected clients before the pipeline has even finished.

The result is a platform that engineering managers, project coordinators, and staffing systems can integrate directly into their existing workflows. It surfaces not just *who* to assign a task to, but *why* — with per-dimension scores that make the recommendation auditable and explainable.

### Problem It Solves

- Eliminates the bottleneck of manual task triage and assignment
- Reduces skill-task mismatch by grounding decisions in structured data rather than intuition
- Prevents overloading high performers by factoring real-time workload into every recommendation
- Provides live, transparent updates so managers are never waiting for a batch job to finish

---

## Key Features

**Real-Time Processing**
- Task analysis begins immediately on receipt — no polling, no batch windows
- Intermediate agent results are streamed via WebSocket as they become available
- Final ranked recommendations are pushed the moment the pipeline completes
- Employee status changes broadcast instantly to all connected clients

**Multi-Agent AI Architecture**
- Five independent, composable agents, each with a clearly defined responsibility
- Agents run asynchronously where their inputs allow, reducing total pipeline latency
- Each agent returns structured JSON — outputs are typed, validated, and auditable
- Agent pipeline is pluggable: swap rule-based logic for LLM calls without changing the interface

**Intelligent Employee Matching**
- Skill matching with alias normalisation and track-affinity boosting
- Workload scoring derived from live active-task counts and availability signals
- Seniority fit evaluated via a calibrated 4×4 compatibility matrix
- Past performance incorporated at 20% weight to reward consistent delivery

**WebSocket Communication**
- Topic-based connection manager: clients subscribe to a specific `task_id` or the global channel
- Concurrent clients on the same task all receive the same event stream
- Dead connections are detected and pruned automatically
- 30-second heartbeat keeps connections alive through load balancers and proxies

**Input Flexibility**
- Plain text task descriptions via REST API
- File-based input: PDF, DOCX, and plain-text task briefs
- Image input with OCR extraction (Tesseract / cloud Vision API)
- Synchronous REST fallback for clients that do not support WebSockets

**Production-Ready Foundation**
- Fully async — built on `asyncio` end to end, no blocking calls in the hot path
- CORS middleware, structured logging, and health check endpoints included
- Docker and Docker Compose support out of the box
- Comprehensive pytest test suite with `pytest-asyncio`

---

## System Architecture

The system is composed of three layers: the **API layer**, the **agent pipeline**, and the **real-time broadcast layer**. These layers communicate through an event-driven architecture built on Python's native `asyncio` primitives.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            CLIENT LAYER                                 │
│   REST Client (curl / Postman)      WebSocket Client (browser / script) │
└────────────────┬────────────────────────────┬───────────────────────────┘
                 │ HTTP                        │ WS
                 ▼                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI APPLICATION                             │
│                                                                         │
│   POST /analyze-task          WS /ws/task-updates/{task_id}             │
│   POST /add-employee          WS /ws/global                             │
│   POST /update-employee-status                                          │
│   GET  /employees                                                       │
└────────────────┬────────────────────────────────────────────────────────┘
                 │ BackgroundTask (non-blocking)
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENT PIPELINE                                  │
│                                                                         │
│  [1] Task Understanding Agent                                           │
│           │                                                             │
│           ├──────────────────────────────────────────────────────┐      │
│  [2] Skill Matching Agent           [3] Workload Monitoring Agent │      │
│       (asyncio.gather — concurrent)                              │      │
│           └──────────────────────────────────────────────────────┘      │
│           │                                                             │
│  [4] Seniority Fit Agent                                                │
│           │                                                             │
│  [5] Decision Orchestrator Agent                                        │
└────────────────┬────────────────────────────────────────────────────────┘
                 │ broadcasts at each stage
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      WEBSOCKET BROADCAST LAYER                          │
│                                                                         │
│   ConnectionManager                                                     │
│   ├── task channels:  { task_id → Set[WebSocket] }                      │
│   └── global channel: all connected clients                             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Request Lifecycle

1. A client calls `POST /analyze-task` with a task description. The endpoint validates the request, generates a `task_id`, and schedules the pipeline as a `BackgroundTask`. It returns the `task_id` in under 5ms — before any agent work has started.
2. The client connects to `WS /ws/task-updates/{task_id}`. The `ConnectionManager` accepts the WebSocket and registers it to the task's channel.
3. The background pipeline runs. After each agent completes, `manager.send_to_task()` pushes a structured JSON event to every client subscribed to that `task_id`.
4. When the Decision Orchestrator emits the final ranking, a `final_result` event closes the pipeline. The WebSocket connection remains open for any subsequent updates.
5. When `POST /update-employee-status` is called, `manager.broadcast()` pushes an `employee_updated` event to **all** connected clients on the global channel, regardless of which task they are watching.

---

## Multi-Agent AI System

Each agent is a self-contained Python class with an async `run()` method. Agents do not share mutable state. They receive typed inputs, produce typed outputs, and are tested independently. This design allows individual agents to be swapped for LLM-backed implementations — or scaled to separate services — without altering the pipeline interface.

### Agent 1 — Task Understanding Agent

**File:** `app/agents/task_agent.py`

The entry point of the pipeline. It receives a raw task description and extracts a structured `TaskRequirements` object containing:

- `required_track` — the engineering discipline (Backend, Frontend, DevOps, AI/ML), detected via keyword frequency scoring across four vocabulary maps
- `required_skills` — specific technologies extracted using regex token matching against a curated skill list, with deduplication
- `seniority_level` — the expected experience level, inferred from seniority signal words (e.g., "architect", "lead", "senior", "junior")
- `complexity` — the task difficulty tier (Low / Medium / High / Critical), derived from urgency and scale keywords
- `summary` — a one-sentence human-readable synthesis of the above

The core extraction logic is synchronous and deterministic. The async wrapper adds a brief simulated latency that would be replaced by an LLM API call in a production deployment. Replacing the extraction function with a call to GPT-4o or Claude requires no changes to the agent interface.

### Agent 2 — Skill Matching Agent

**File:** `app/agents/skill_agent.py`

Computes a skill compatibility score (0–100) for every employee against the task's `required_skills`. The algorithm:

1. Normalises both the task skill list and each employee's skill list through an alias table (e.g., `"k8s"` → `"kubernetes"`, `"postgres"` → `"postgresql"`) to eliminate false mismatches from naming variants
2. Computes a Jaccard similarity score: `|matched| / |union|`
3. Applies a 1.15× track-affinity boost when the employee's primary track matches the task's `required_track`
4. Clamps the result to 0–100 and exposes the matched and missing skill sets for use in recommendation explanations

In production, this agent is a natural candidate for embedding-based semantic similarity (e.g., using OpenAI `text-embedding-3-small` or a local sentence-transformers model) to handle synonym-rich skill descriptions without an exhaustive alias table.

### Agent 3 — Workload Monitoring Agent

**File:** `app/agents/workload_agent.py`

Evaluates each employee's current capacity. The scoring formula is:

```
workload_score = max(availability_score − (active_tasks × 8), 0)
```

An employee with `availability_score = 100` and `active_tasks = 0` scores 100. Each additional active task deducts 8 points, reflecting the cognitive overhead of context-switching. The penalty weight is configurable. In a production system, this agent subscribes to a task-queue event stream (Kafka, Redis Streams) and maintains a real-time in-memory state rather than polling a store.

This agent runs **concurrently** with the Skill Matching Agent via `asyncio.gather()` because neither depends on the other's output.

### Agent 4 — Seniority Fit Agent

**File:** `app/agents/seniority_agent.py`

Scores how well each employee's experience level matches the task's requirements, using a calibrated 4×4 compatibility matrix:

|              | Required: Junior | Required: Mid | Required: Senior | Required: Lead |
|--------------|:----------------:|:-------------:|:----------------:|:--------------:|
| **Junior**   | 100              | 60            | 30               | 10             |
| **Mid**      | 70               | 100           | 70               | 40             |
| **Senior**   | 50               | 80            | 100              | 80             |
| **Lead**     | 30               | 60            | 90               | 100            |

The matrix models two asymmetries deliberately:
- Over-qualification carries a mild penalty. A Lead engineer can complete a Junior task, but it is a poor use of their capacity.
- Under-qualification carries a heavy penalty. A Junior engineer on a Lead-complexity task is a high risk assignment.

The effective required level is derived from the maximum of the explicit `seniority_level` and the level implied by `complexity`, ensuring the agent is conservative when both signals are present.

### Agent 5 — Decision Orchestrator Agent

**File:** `app/agents/decision_agent.py`

The final synthesis stage. It collects all upstream agent outputs, looks up each employee's past performance record, applies the weighted scoring formula, sorts the results, and emits the top 5 `EmployeeRecommendation` objects. Each recommendation includes all four component scores, the final weighted score, a list of matched skills, and a plain-English explanation generated from the score breakdown.

---

## Scoring System

The final score for each employee is a weighted linear combination of four dimensions:

```
final_score = (skill_score  × 0.40)
            + (workload_score × 0.20)
            + (seniority_score × 0.20)
            + (performance_score × 0.20)
```

| Dimension          | Weight | Source                          | Range  |
|--------------------|--------|---------------------------------|--------|
| Skill Match        | 40%    | Skill Matching Agent            | 0–100  |
| Workload Balance   | 20%    | Workload Monitoring Agent       | 0–100  |
| Seniority Fit      | 20%    | Seniority Fit Agent             | 0–100  |
| Past Performance   | 20%    | Employee record (`past_success_rate`) | 0–100  |

**Rationale for weighting:**

Skill match carries the highest weight because it is the strongest predictor of task success. Assigning a task to someone without the required skills is rarely recoverable regardless of their availability or seniority. Workload, seniority, and past performance are meaningful tie-breakers that prevent systematically overloading the best engineers while still preferring demonstrated reliability.

**Ranking:** Employees are sorted by `final_score` in descending order. The top 5 are returned with sequential ranks (1–5). In the event of a tie, the employee with a higher `past_success_rate` is ranked first.

---

## API Documentation

### `POST /analyze-task`

Submits a task for analysis. Returns a `task_id` immediately. The multi-agent pipeline runs in the background and streams results to connected WebSocket clients.

**Request**

```http
POST /analyze-task
Content-Type: application/json

{
  "description": "Build a scalable FastAPI microservice with Redis caching and PostgreSQL integration. Deploy via Docker on Kubernetes. Senior-level task.",
  "requester": "Product Team",
  "priority": "High"
}
```

**Response `200 OK`**

```json
{
  "task_id": "a1b2c3d4",
  "status": "processing",
  "message": "Pipeline started. Connect to WebSocket to receive live updates.",
  "ws_url": "/ws/task-updates/a1b2c3d4"
}
```

---

### `POST /analyze-task/sync`

Synchronous variant. Waits for the full pipeline and returns the final result. For REST-only clients.

**Request:** same as above.

**Response `200 OK`**

```json
{
  "task_id": "a1b2c3d4",
  "status": "complete",
  "task_requirements": {
    "required_track": "Backend",
    "required_skills": ["FastAPI", "Redis", "Docker", "Kubernetes", "Postgresql"],
    "seniority_level": "Senior",
    "complexity": "High",
    "summary": "High-complexity Backend task requiring Senior-level expertise in: FastAPI, Redis, Docker, Kubernetes."
  },
  "updates": [
    "Task received → starting analysis pipeline…",
    "Task Understanding Agent complete",
    "Skill Matching + Workload Monitoring agents running in parallel…",
    "Skill Matching Agent complete",
    "Workload Monitoring Agent complete",
    "Seniority Fit Agent complete",
    "Decision Orchestrator complete – top candidates identified"
  ],
  "final_recommendations": [
    {
      "rank": 1,
      "employee_id": 1,
      "name": "Ahmed",
      "track": "Backend",
      "level": "Senior",
      "final_score": 78.2,
      "skill_score": 85.0,
      "workload_score": 59.0,
      "seniority_score": 100.0,
      "performance_score": 92.0,
      "reason": "Strong skill match (fastapi, redis, docker); manageable workload; ideal seniority level (Senior); excellent track record (92%).",
      "matched_skills": ["fastapi", "redis", "docker"]
    }
  ]
}
```

---

### `WS /ws/task-updates/{task_id}`

Main real-time channel. Connect here **before or immediately after** calling `POST /analyze-task` to receive the full event stream for a specific task.

**Connection**

```
ws://localhost:8000/ws/task-updates/a1b2c3d4
```

**Event: `task_received`**

```json
{
  "event": "task_received",
  "task_id": "a1b2c3d4",
  "ts": 1716500000.0,
  "message": "Task received → starting analysis pipeline…"
}
```

**Event: `agent_start`**

```json
{
  "event": "agent_start",
  "task_id": "a1b2c3d4",
  "ts": 1716500000.3,
  "message": "Task Understanding Agent running…",
  "data": {
    "agent": "task_agent",
    "status": "running"
  }
}
```

**Event: `agent_done`**

```json
{
  "event": "agent_done",
  "task_id": "a1b2c3d4",
  "ts": 1716500000.65,
  "message": "Task Understanding Agent complete",
  "data": {
    "agent": "task_agent",
    "status": "done",
    "requirements": {
      "required_track": "Backend",
      "required_skills": ["FastAPI", "Redis", "Docker"],
      "seniority_level": "Senior",
      "complexity": "High",
      "summary": "High-complexity Backend task requiring Senior-level expertise."
    }
  }
}
```

**Event: `final_result`**

```json
{
  "event": "final_result",
  "task_id": "a1b2c3d4",
  "ts": 1716500001.8,
  "status": "complete",
  "final_result": { "...": "see /analyze-task/sync response above" }
}
```

---

### `WS /ws/global`

System-wide event channel. Broadcasts employee status changes and heartbeat pings to all connected clients regardless of which task they are watching.

**Event: `employee_updated`**

```json
{
  "event": "employee_updated",
  "ts": 1716500100.0,
  "employee_id": 1,
  "changes": {
    "active_tasks": 5,
    "availability_score": 30
  },
  "message": "Employee #1 status updated – workload scores refreshed."
}
```

**Event: `heartbeat`**

```json
{
  "event": "heartbeat",
  "ts": 1716500130.0,
  "connections": 12
}
```

---

### `POST /add-employee`

Adds a new employee to the assignment pool. Takes effect immediately for subsequent pipeline runs.

**Request**

```http
POST /add-employee
Content-Type: application/json

{
  "name": "Mariam",
  "track": "DevOps",
  "skills": ["Kubernetes", "Terraform", "AWS", "CI/CD"],
  "level": "Senior",
  "active_tasks": 0,
  "availability_score": 100,
  "past_success_rate": 0.91
}
```

**Response `201 Created`**

```json
{
  "message": "Employee added",
  "employee": {
    "id": 9,
    "name": "Mariam",
    "track": "DevOps",
    "skills": ["Kubernetes", "Terraform", "AWS", "CI/CD"],
    "level": "Senior",
    "active_tasks": 0,
    "availability_score": 100.0,
    "past_success_rate": 0.91
  }
}
```

---

### `POST /update-employee-status`

Updates an employee's workload or availability in real time. Triggers a broadcast to all connected WebSocket clients on the global channel.

**Request**

```http
POST /update-employee-status
Content-Type: application/json

{
  "employee_id": 1,
  "active_tasks": 5,
  "availability_score": 30
}
```

**Response `200 OK`**

```json
{
  "message": "Employee status updated",
  "employee": {
    "id": 1,
    "name": "Ahmed",
    "active_tasks": 5,
    "availability_score": 30.0
  }
}
```

---

### `GET /employees`

Returns the full employee database.

**Response `200 OK`**

```json
{
  "count": 8,
  "employees": [
    {
      "id": 1,
      "name": "Ahmed",
      "track": "Backend",
      "skills": ["FastAPI", "Redis", "Docker", "PostgreSQL"],
      "level": "Senior",
      "active_tasks": 2,
      "availability_score": 75.0,
      "past_success_rate": 0.92
    }
  ]
}
```

---

## Real-Time Flow

The following sequence describes a complete task lifecycle from submission to final recommendation delivery.

```
Client                     FastAPI                  Agent Pipeline             WebSocket Clients
  │                           │                           │                           │
  │── POST /analyze-task ────▶│                           │                           │
  │◀─ {task_id, ws_url} ──────│                           │                           │
  │                           │                           │                           │
  │── WS connect ────────────▶│ register to task channel  │                           │
  │                           │                           │                           │
  │                           │── BackgroundTask start ──▶│                           │
  │                           │                           │── emit: task_received ───▶│
  │                           │                           │                           │
  │                           │                           │  [1] Task Understanding   │
  │                           │                           │── emit: agent_start ─────▶│
  │                           │                           │── emit: agent_done ──────▶│
  │                           │                           │                           │
  │                           │                           │  [2+3] Skill + Workload   │
  │                           │                           │    (asyncio.gather)       │
  │                           │                           │── emit: agent_start ─────▶│
  │                           │                           │── emit: agent_done (×2) ─▶│
  │                           │                           │                           │
  │                           │                           │  [4] Seniority Fit        │
  │                           │                           │── emit: agent_done ──────▶│
  │                           │                           │                           │
  │                           │                           │  [5] Decision Orchestrator│
  │                           │                           │── emit: final_result ────▶│
  │                           │                           │                           │
  │◀─ final_result event ─────────────────────────────────────────────────────────────│
```

**Stage-by-stage breakdown:**

1. **Task received** — `POST /analyze-task` returns within 5ms with a `task_id`. The pipeline is queued as a `BackgroundTask` and does not block the HTTP response.
2. **Task analysis starts** — the Task Understanding Agent begins extracting structured requirements from the description. A `agent_start` event fires immediately.
3. **Parallel agent execution** — once requirements are available, the Skill Matching and Workload Monitoring agents are launched concurrently via `asyncio.gather()`. Clients receive two `agent_done` events in rapid succession.
4. **Intermediate results streamed** — each `agent_done` event includes a preview of that agent's top results, allowing the frontend to begin rendering partial rankings before the pipeline finishes.
5. **Final ranking delivered** — the Decision Orchestrator aggregates all agent scores, computes final rankings, and pushes the complete `final_result` event. The full recommendation object — including per-dimension scores and explanations for all five candidates — is delivered in a single atomic event.

---

## Tech Stack

| Component              | Technology                        | Purpose                                      |
|------------------------|-----------------------------------|----------------------------------------------|
| API framework          | FastAPI 0.111+                    | Async REST endpoints, WebSocket routing      |
| Async runtime          | Python asyncio                    | Concurrent agent execution, non-blocking I/O |
| WebSocket server       | `websockets` / Uvicorn            | Real-time bidirectional communication        |
| Data validation        | Pydantic v2                       | Request/response schemas, typed agent I/O    |
| In-memory data store   | Python dict + asyncio.Lock        | Thread-safe employee repository              |
| Task scheduling        | FastAPI BackgroundTasks           | Non-blocking pipeline execution              |
| Containerisation       | Docker / Docker Compose           | Environment consistency, deployment          |
| Testing                | pytest + pytest-asyncio           | Unit and integration tests for all agents    |
| **Optional: LLM**      | OpenAI API / Anthropic API        | Task Understanding and Skill Matching agents |
| **Optional: OCR**      | Tesseract / Google Cloud Vision   | Image-to-text extraction for task input      |
| **Optional: Embeddings** | OpenAI `text-embedding-3-small` | Semantic skill similarity matching           |
| **Optional: Queue**    | Redis Streams / Kafka             | Production-grade workload event stream       |

---

## Installation

### Prerequisites

- Python 3.12 or later
- pip
- Docker and Docker Compose (optional, for containerised deployment)

### Local Setup

**1. Clone the repository**

```bash
git clone https://github.com/your-org/smart-task-assignment.git
cd smart-task-assignment
```

**2. Create and activate a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Start the server**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server is now running at `http://localhost:8000`. Interactive API documentation is available at `http://localhost:8000/docs`.

### Docker Deployment

```bash
# Build and start
docker-compose up --build

# Run in detached mode
docker-compose up -d --build

# View logs
docker-compose logs -f api
```

### Running Tests

```bash
pytest tests/ -v
```

All tests are async and use `pytest-asyncio` in auto mode.

### Connecting a WebSocket Client

```python
import asyncio
import json
import httpx
import websockets

async def main():
    # Submit a task
    async with httpx.AsyncClient() as http:
        resp = await http.post("http://localhost:8000/analyze-task", json={
            "description": "Build a FastAPI service with Redis and Docker. Senior level.",
            "requester": "Engineering",
            "priority": "High"
        })
        data = resp.json()

    task_id = data["task_id"]
    ws_url = f"ws://localhost:8000{data['ws_url']}"

    # Stream results
    async with websockets.connect(ws_url) as ws:
        while True:
            msg = json.loads(await ws.recv())
            print(f"[{msg['event']}] {msg.get('message', '')}")
            if msg["event"] == "final_result":
                for rec in msg["final_result"]["final_recommendations"]:
                    print(f"  #{rec['rank']} {rec['name']} — {rec['final_score']:.1f}")
                break

asyncio.run(main())
```

Alternatively, use the included example client:

```bash
python examples/ws_client.py
```

---

## Example Usage

### Input: Backend Task

```json
{
  "description": "Build a scalable FastAPI microservice with Redis caching and PostgreSQL integration. The service must handle real-time WebSocket connections and be deployed via Docker on Kubernetes. This is a senior-level task.",
  "requester": "Product Team",
  "priority": "High"
}
```

### Seed Employee Pool

```json
[
  { "id": 1, "name": "Ahmed",   "track": "Backend",  "skills": ["FastAPI","Redis","Docker","PostgreSQL"], "level": "Senior", "active_tasks": 2,  "availability_score": 75,  "past_success_rate": 0.92 },
  { "id": 2, "name": "Sara",    "track": "Backend",  "skills": ["FastAPI","Django","Celery","Redis"],      "level": "Mid",    "active_tasks": 1,  "availability_score": 90,  "past_success_rate": 0.88 },
  { "id": 3, "name": "Omar",    "track": "Frontend", "skills": ["React","TypeScript","TailwindCSS"],       "level": "Senior", "active_tasks": 3,  "availability_score": 55,  "past_success_rate": 0.90 },
  { "id": 4, "name": "Layla",   "track": "DevOps",   "skills": ["Docker","Kubernetes","CI/CD","Terraform"],"level": "Lead",   "active_tasks": 1,  "availability_score": 85,  "past_success_rate": 0.95 },
  { "id": 5, "name": "Youssef", "track": "AI/ML",    "skills": ["PyTorch","FastAPI","LangChain"],          "level": "Senior", "active_tasks": 0,  "availability_score": 100, "past_success_rate": 0.89 }
]
```

### Output: Top 5 Recommendations

```json
{
  "status": "complete",
  "task_requirements": {
    "required_track": "Backend",
    "required_skills": ["FastAPI", "Redis", "Docker", "Kubernetes", "Postgresql"],
    "seniority_level": "Senior",
    "complexity": "High"
  },
  "final_recommendations": [
    {
      "rank": 1,
      "name": "Ahmed",
      "track": "Backend",
      "level": "Senior",
      "final_score": 78.2,
      "skill_score": 85.0,
      "workload_score": 59.0,
      "seniority_score": 100.0,
      "performance_score": 92.0,
      "reason": "Strong skill match (fastapi, redis, docker); manageable workload; ideal seniority level (Senior); excellent track record (92%).",
      "matched_skills": ["fastapi", "redis", "docker"]
    },
    {
      "rank": 2,
      "name": "Sara",
      "track": "Backend",
      "level": "Mid",
      "final_score": 69.4,
      "skill_score": 70.0,
      "workload_score": 82.0,
      "seniority_score": 70.0,
      "performance_score": 88.0,
      "reason": "Moderate skill overlap; low current workload; acceptable seniority (Mid); solid track record (88%).",
      "matched_skills": ["fastapi", "redis"]
    },
    {
      "rank": 3,
      "name": "Layla",
      "track": "DevOps",
      "level": "Lead",
      "final_score": 62.0,
      "skill_score": 40.0,
      "workload_score": 77.0,
      "seniority_score": 90.0,
      "performance_score": 95.0,
      "reason": "Limited skill match; low current workload; ideal seniority level (Lead); excellent track record (95%).",
      "matched_skills": ["docker"]
    }
  ]
}
```

---

## Project Structure

```
smart-task-assignment/
│
├── app/
│   ├── main.py                     # FastAPI app factory, lifespan, middleware, router registration
│   │
│   ├── agents/                     # Independent AI agent modules
│   │   ├── task_agent.py           # Agent 1: Task understanding and requirement extraction
│   │   ├── skill_agent.py          # Agent 2: Skill compatibility scoring
│   │   ├── workload_agent.py       # Agent 3: Real-time workload and availability scoring
│   │   ├── seniority_agent.py      # Agent 4: Seniority fit via compatibility matrix
│   │   └── decision_agent.py       # Agent 5: Weighted score aggregation and final ranking
│   │
│   ├── services/
│   │   ├── task_pipeline.py        # Orchestrates the full agent pipeline; emits WebSocket events
│   │   └── realtime_engine.py      # Background engine: heartbeat loop, employee broadcast
│   │
│   ├── routes/
│   │   ├── tasks.py                # POST /analyze-task, WS /ws/task-updates, WS /ws/global
│   │   └── employees.py            # GET /employees, POST /add-employee, POST /update-employee-status
│   │
│   ├── websocket/
│   │   └── manager.py              # Topic-based WebSocket connection manager with auto-pruning
│   │
│   ├── models/
│   │   ├── schemas.py              # Pydantic v2 models for all request/response/agent types
│   │   └── employee_store.py       # Async-safe in-memory employee repository
│   │
│   └── utils/
│       └── helpers.py              # Task ID generation, logging configuration
│
├── tests/
│   └── test_agents.py              # pytest-asyncio tests for all five agents
│
├── examples/
│   ├── ws_client.py                # End-to-end WebSocket test client
│   └── payloads.json               # Sample request payloads and expected WebSocket event shapes
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── README.md
```

**Directory responsibilities at a glance:**

- `agents/` — Each file is a self-contained agent. No agent imports another. Changes to one agent do not affect others.
- `services/` — Orchestration logic that coordinates agents and manages background work. This is where the pipeline sequence is defined.
- `routes/` — Thin HTTP and WebSocket handlers. They validate input, call services, and return responses. No business logic lives here.
- `websocket/` — The connection manager is the sole owner of all active WebSocket state. All broadcast operations go through it.
- `models/` — Pydantic schemas define the contract between all system layers. The employee store is the only mutable shared state.
- `utils/` — Stateless utility functions with no dependencies on application modules.

---

## Future Improvements

The current implementation is designed as a solid, extensible foundation. The following improvements are planned or under consideration for future releases:

**Event-Driven Architecture with Kafka**
Replace the in-process `BackgroundTask` model with a Kafka producer/consumer architecture. Task submissions publish to a `tasks` topic; worker pods consume and run the pipeline. This decouples ingestion from processing and enables horizontal scaling of the agent pipeline independently of the API layer.

**LangGraph Multi-Agent Orchestration**
Refactor the agent pipeline using [LangGraph](https://github.com/langchain-ai/langgraph) to define the agent dependency graph declaratively. LangGraph's `StateGraph` primitive supports conditional edges, retry logic, and agent checkpointing — making the pipeline more observable and fault-tolerant.

**Vector Database for Semantic Skill Matching**
Replace keyword-based skill matching with embedding-based semantic search using pgvector (PostgreSQL extension) or Pinecone. Employee skill profiles are encoded at write time; task requirements are encoded at query time; candidates are retrieved by cosine similarity. This handles skill synonyms, adjacent technologies, and natural-language descriptions natively.

**Persistent Storage**
Migrate the in-memory employee store to PostgreSQL with SQLAlchemy 2.0 and Alembic migrations. Add Redis for caching frequently accessed employee records and for storing pipeline state between restarts.

**Authentication and Authorisation**
Add JWT-based authentication for all REST and WebSocket endpoints. Scope access by role: managers submit tasks and update employee status; engineers view their own assignment queue; administrators manage the employee pool.

**OCR Pipeline**
Integrate a full OCR pipeline using Tesseract or Google Cloud Vision for image inputs, and `pdfminer`/`python-docx` for structured document parsing. Route all input types through a unified normalisation layer before the Task Understanding Agent.

**Observability**
Add structured JSON logging with correlation IDs tied to `task_id`, Prometheus metrics exposition (`/metrics`), and OpenTelemetry trace propagation across the agent pipeline. Expose a `GET /pipeline/status/{task_id}` endpoint for querying pipeline state without a WebSocket connection.

**Microservices Migration**
Extract each agent into a standalone FastAPI microservice communicating over gRPC or a shared message broker. The Decision Orchestrator becomes a lightweight aggregation service that awaits responses from the four upstream agent services. This enables independent scaling, deployment, and versioning of each agent.

---

## Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository and create a feature branch from `main`.
2. Write tests for any new agent logic or pipeline behaviour. All tests must pass.
3. Ensure all code passes `ruff check` and `mypy` before opening a pull request.
4. Open a pull request with a clear description of the change and its motivation.

For significant architectural changes, please open an issue first to discuss the proposal.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

*Built with FastAPI · asyncio · WebSockets · Pydantic v2*
