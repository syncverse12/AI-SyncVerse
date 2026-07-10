# Smart Task Assignment System

Real-time, multi-agent FastAPI microservice that analyzes a task description and recommends the best-fit employees to assign it to — with live progress streamed over WebSocket as each agent completes.

Part of the **SyncVerse** platform.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Scoring Model](#scoring-model)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [WebSocket Events](#websocket-events)
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [Running with Docker](#running-with-docker)
- [Deploying to Railway](#deploying-to-railway)
- [Testing](#testing)
- [Known Limitations](#known-limitations)

---

## Overview

You submit a task description in plain text (e.g. *"Build a scalable FastAPI microservice with Redis caching, deploy on Kubernetes, senior-level"*), and the system returns a ranked, explainable shortlist of the best-fit employees — not a black-box pick.

Two ways to consume it:

| Mode | Endpoint | Use case |
|---|---|---|
| **Streaming** | `POST /analyze-task` + `WS /ws/task-updates/{task_id}` | Live progress UI, agent-by-agent updates |
| **Synchronous** | `POST /analyze-task/sync` | Simple REST clients, scripts, testing |

No external API keys are required — the pipeline is fully rule-based and runs entirely in-process.

---

## Architecture

Five independent agents run in sequence (two of them concurrently), each streaming its own completion event:

```
Task submitted
     │
     ▼
[1] Task Understanding Agent   → parses free text into structured requirements
     │
     ├──► [2] Skill Matching Agent      ┐
     │                                   │  run concurrently (asyncio.gather)
     └──► [3] Workload Monitoring Agent ┘
     │
     ▼
[4] Seniority Fit Agent        → matches employee level to task complexity
     │
     ▼
[5] Decision Orchestrator Agent → merges all scores, returns top 5 ranked
```

| # | Agent | File | What it does |
|---|---|---|---|
| 1 | Task Understanding | `app/agents/task_agent.py` | Keyword-based extraction: track, required skills, seniority, complexity. Designed to be swapped for an LLM call without changing the interface. |
| 2 | Skill Matching | `app/agents/skill_agent.py` | Jaccard similarity between task skills and employee skills, with alias normalization (`k8s` → `kubernetes`) and a track-match boost. |
| 3 | Workload Monitoring | `app/agents/workload_agent.py` | `availability_score − (active_tasks × 8)`, clamped to 0–100. |
| 4 | Seniority Fit | `app/agents/seniority_agent.py` | 4×4 calibrated compatibility matrix (Junior/Mid/Senior/Lead); under-qualification penalized more than over-qualification. |
| 5 | Decision Orchestrator | `app/agents/decision_agent.py` | Weighted final score + human-readable reasoning per candidate. |

---

## Scoring Model

```
final_score = skill_match × 0.40
            + workload    × 0.20
            + seniority   × 0.20
            + past_perf   × 0.20
```

Skill match is weighted highest as the strongest predictor of task success; the rest act as tie-breakers. Top 5 candidates are returned, each with a `reason` string and the list of `matched_skills`.

> **Note:** if the task description contains no recognizable technical keywords, the Skill Matching Agent returns a neutral score (50) instead of a false zero, so workload/seniority/performance can still meaningfully differentiate candidates.

---

## Project Structure

```
smart-task-assignment/
├── app/
│   ├── main.py                  # FastAPI app, CORS, lifespan, global exception handler
│   ├── core/
│   │   └── config.py             # Environment-driven settings (pydantic-settings)
│   ├── agents/
│   │   ├── task_agent.py         # Agent 1
│   │   ├── skill_agent.py        # Agent 2
│   │   ├── workload_agent.py     # Agent 3
│   │   ├── seniority_agent.py    # Agent 4
│   │   └── decision_agent.py     # Agent 5
│   ├── models/
│   │   ├── schemas.py            # Pydantic models
│   │   └── employee_store.py     # In-memory employee repository
│   ├── routes/
│   │   ├── tasks.py               # /analyze-task, /analyze-task/sync, WS routes
│   │   └── employees.py           # /employees, /add-employee, /update-employee-status
│   ├── services/
│   │   ├── task_pipeline.py       # Orchestrates the 5-agent pipeline
│   │   └── realtime_engine.py     # Heartbeat + employee-change broadcasts
│   ├── websocket/
│   │   └── manager.py             # Per-task + global WS connection manager
│   └── utils/
│       └── helpers.py             # Logging config, task ID generation
├── tests/
│   └── test_agents.py            # 12 tests covering all 5 agents + pipeline
├── examples/
│   └── ws_client.py              # Example end-to-end WebSocket client
├── Dockerfile
├── docker-compose.yml
├── railway.json
├── requirements.txt              # Runtime dependencies
├── requirements-dev.txt          # + pytest, httpx (testing only)
└── .env.example
```

---

## API Reference

### `POST /analyze-task`
Submit a task; returns immediately with a `task_id` while the pipeline runs in the background.

**Request**
```json
{
  "description": "Build a scalable FastAPI microservice with Redis caching, senior-level",
  "requester": "Product Team",
  "priority": "High"
}
```
`description` is required, 1–5000 characters.

**Response `200`**
```json
{
  "task_id": "07bddf2d",
  "status": "processing",
  "message": "Pipeline started. Connect to WebSocket to receive live updates.",
  "ws_url": "/ws/task-updates/07bddf2d"
}
```

### `POST /analyze-task/sync`
Same input, but waits for the full pipeline and returns the final result directly — no WebSocket needed. Returns `500` with a safe error body if the pipeline fails internally.

### `GET /employees`
List all employees currently in the store.

### `POST /add-employee`
Add a new employee. Returns `201`.

### `POST /update-employee-status`
Update `active_tasks`, `availability_score`, or `past_success_rate` for an employee. Broadcasts an `employee_updated` event to all WebSocket clients. Returns `404` if the employee doesn't exist.

### `GET /health`
Returns service status and current WebSocket connection count. Used as the container health check.

Full interactive docs available at **`/docs`** once running.

---

## WebSocket Events

### `WS /ws/task-updates/{task_id}`
Subscribe before or right after calling `POST /analyze-task` to receive every stage of that task's pipeline:

| Event | Meaning |
|---|---|
| `task_received` | Pipeline started |
| `agent_start` | An agent (or pair of agents) began running |
| `agent_done` | An agent finished — includes a preview of its output |
| `final_result` | Pipeline complete — includes the full ranked recommendation list |
| `error` | Pipeline failed — includes a safe, generic error message |

### `WS /ws/global`
Subscribe to system-wide events: `employee_updated`, `heartbeat` (every 30s).

See `examples/ws_client.py` for a complete working client.

---

## Configuration

All configuration is environment-driven (`app/core/config.py`) — nothing is hardcoded to `localhost` or a fixed port.

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | Server port. Railway injects this automatically. |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `ENVIRONMENT` | `development` | `development` \| `production` |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `CORS_ALLOW_CREDENTIALS` | `false` | Must stay `false` if `CORS_ORIGINS=*` (browser requirement) |

Copy `.env.example` to `.env` for local runs. No API keys are required — the pipeline has no external dependencies.

---

## Running Locally

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements-dev.txt
cp .env.example .env

uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs`.

---

## Running with Docker

```bash
docker compose up --build
```

Runs on `http://localhost:8000`, non-root container user, built-in health check at `/health`.

---

## Deploying to Railway

1. Push this repository (Railway auto-detects the `Dockerfile`).
2. No environment variables are required to boot — `PORT` is injected automatically.
3. Optionally set `CORS_ORIGINS` to your frontend's real domain once you have one.
4. `railway.json` already points Railway's health check at `/health`.

---

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

12 tests covering all 5 agents individually plus end-to-end decision-agent behavior (ranking order, top-5 limit, score bounds).

---

## Known Limitations

- **In-memory store**: employee data resets on every restart/redeploy. Fine for a demo/graduation-project scope; swap `employee_store.py` for a real database before any production use.
- **Single worker**: the store is not process-safe across multiple workers/replicas. `Dockerfile` intentionally runs `--workers 1`; horizontal scaling on Railway would require moving state to an external store first.
- **Rule-based NLP**: Agent 1 uses keyword matching, not an LLM. `_extract_requirements` is deliberately isolated so it can be swapped for a Gemini/OpenAI call later without touching the rest of the pipeline.
