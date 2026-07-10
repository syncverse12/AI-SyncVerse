# 🧠 AI Dynamic Project Planner

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![HuggingFace](https://img.shields.io/badge/🤗%20Hugging%20Face-Spaces-FFD21E)
![License](https://img.shields.io/badge/License-MIT-green)

**Production-ready FastAPI service that builds, optimises, and dynamically replans
project timelines — no ML training required.**

</div>

---

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              ← FastAPI app factory + uvicorn entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        ← All HTTP route handlers
│   ├── core/
│   │   ├── __init__.py
│   │   └── planner.py       ← Adapter: Pydantic ↔ engine dataclasses + store
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py       ← Pydantic v2 request/response schemas
│   └── utils/
│       ├── __init__.py
│       └── version.py       ← VERSION constant
│
├── planner/
│   ├── __init__.py          ← Public engine API
│   ├── models.py            ← Task, Resource, Sprint, ProjectPlan dataclasses
│   └── engine.py            ← DAG, CPM, Scheduler, Sprints, Replan, Facade
│
├── Dockerfile               ← HF Spaces-compatible, port 7860
├── requirements.txt         ← fastapi · uvicorn · pydantic
└── README.md
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `POST` | `/plan` | **Create a new AI project plan** |
| `GET` | `/plan/{project_id}` | Retrieve an existing plan |
| `GET` | `/plan/{project_id}/summary` | Lightweight summary |
| `POST` | `/plan/{project_id}/replan` | Apply a change event |
| `DELETE` | `/plan/{project_id}` | Delete a project |
| `GET` | `/plans` | List all projects |

Swagger UI → `/docs` · ReDoc → `/redoc`

---

## Run Locally

```bash
git clone https://github.com/your-org/ai-planner.git
cd ai-planner

pip install -r requirements.txt

uvicorn app.main:app --reload --port 7860
# Open http://localhost:7860/docs
```

---

## Docker

```bash
docker build -t ai-planner .
docker run -p 7860:7860 ai-planner
```

---

## Deploy to Hugging Face Spaces

1. Create a new Space → choose **Docker** SDK
2. Push your files:

```bash
git clone https://huggingface.co/spaces/YOUR_NAME/YOUR_SPACE
cp -r . YOUR_SPACE/
cd YOUR_SPACE && git add . && git commit -m "Deploy" && git push
```

HF detects the `Dockerfile`, builds it, and starts on port **7860** automatically.

---

## Example Usage

### Create a plan

```bash
curl -X POST http://localhost:7860/plan \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "SaaS MVP",
    "deadline": "2025-09-01",
    "tasks": [
      { "id":"t1", "name":"Design Architecture", "priority":"high",
        "estimated_hours":16, "required_skills":["backend"] },
      { "id":"t2", "name":"Implement API", "priority":"high",
        "estimated_hours":40, "required_skills":["backend","python"],
        "dependencies":["t1"] },
      { "id":"t3", "name":"Deploy", "priority":"critical",
        "estimated_hours":4, "required_skills":["devops"],
        "dependencies":["t2"] }
    ],
    "resources": [
      { "id":"r1", "name":"Alice", "capacity":1.0, "skills":["backend","python"] },
      { "id":"r2", "name":"Carol", "capacity":1.0, "skills":["devops"] }
    ]
  }'
```

### Replan after a late task

```bash
curl -X POST http://localhost:7860/plan/{project_id}/replan \
  -H "Content-Type: application/json" \
  -d '{ "event_type": "task_completed_late", "task_id": "t2", "new_value": 64.0 }'
```

### All supported replan events

| `event_type` | `new_value` | `task_id` | `resource_id` |
|---|---|---|---|
| `task_completed_early` | float (actual hours) | ✓ | — |
| `task_completed_late`  | float (actual hours) | ✓ | — |
| `task_added`           | TaskIn dict          | — | — |
| `task_removed`         | —                    | ✓ | — |
| `resource_unavailable` | —                    | — | ✓ |
| `resource_capacity_changed` | float 0–1     | — | ✓ |
| `dependency_changed`   | list of task IDs     | ✓ | — |

---

## License

MIT © 2025
