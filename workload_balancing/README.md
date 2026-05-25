# ⚖️ Dynamic Workload Balancing System

A production-ready FastAPI backend that continuously monitors employee workload,
detects imbalance in task distribution, and generates actionable redistribution
recommendations — streamed in real-time via Server-Sent Events.

> **All recommended actions require human approval. The system never auto-executes changes.**

---

## Architecture

```
app/
├── main.py                         # FastAPI app factory, lifespan, CORS
├── models/
│   └── schemas.py                  # Pydantic v2 models (all I/O contracts)
├── balancing/
│   ├── workload_monitor.py         # Score calculation & risk classification
│   ├── risk_analyzer.py            # Imbalance/bottleneck detection, health score
│   └── redistribution_engine.py   # Recommendation generation
├── services/
│   └── balancer_service.py         # Orchestrator + SSE fan-out broadcast
├── routes/
│   └── balancer_routes.py          # REST + SSE route handlers
└── data/
    └── sample_data.py              # 4 pre-built demo scenarios
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
uvicorn app.main:app --reload --port 8000

# 3. Open interactive docs
open http://localhost:8000/docs
```

---

## API Reference

### `POST /api/v1/workload/analyse`
Submit employee and task data. Returns a `BalanceReport` and broadcasts to all SSE subscribers.

**Request body:**
```json
{
  "employees": [
    {
      "id": 1,
      "name": "Ahmed",
      "active_tasks": 8,
      "delayed_tasks": 3,
      "availability_score": 20,
      "task_complexity_distribution": { "low": 1, "medium": 3, "high": 3, "critical": 1 },
      "past_success_rate": 0.72
    }
  ],
  "tasks": [
    {
      "id": 30,
      "title": "Implement OAuth2 flow",
      "complexity": "high",
      "priority": 8,
      "assigned_to": 1,
      "is_delayed": true,
      "estimated_hours": 10
    }
  ]
}
```

**Response:**
```json
{
  "report": {
    "status": "imbalance_detected",
    "timestamp": "2024-01-15T10:30:00Z",
    "team_health_score": 59.0,
    "overloaded_employees": [
      {
        "employee_name": "Ahmed",
        "risk_score": 100.0,
        "risk_level": "high",
        "reason": "3 delayed tasks; 8 active tasks; availability only 20%",
        "is_overloaded": true,
        "is_bottleneck": false
      }
    ],
    "recommended_actions": [
      {
        "action": "reassign_task",
        "priority": 10,
        "from_employee": "Ahmed",
        "to_employee": "Karim",
        "task_id": 35,
        "task_title": "Code review backlog",
        "reason": "Ahmed has risk score 100. Karim has 85% availability.",
        "estimated_impact": "Reduces Ahmed's workload score by ~15-25 points.",
        "requires_approval": true
      }
    ],
    "summary": "Team of 5 · Health 59/100 · imbalance_detected. ⚠ Overloaded: Ahmed, Lena."
  }
}
```

---

### `GET /api/v1/workload/stream`
Server-Sent Events stream. Connect once and receive all analysis events.

```javascript
const es = new EventSource("http://localhost:8000/api/v1/workload/stream");
es.onmessage = (e) => {
  const event = JSON.parse(e.data);
  // event.event_type: "status_update" | "risk_alert" | "recommendation" | "ping"
  // event.payload: BalanceReport
  console.log(event);
};
```

---

### `GET /api/v1/workload/status`
Returns the last known `BalanceReport`. Polling fallback when SSE is unavailable.

---

### `POST /api/v1/workload/simulate/{scenario}`
Run a pre-built scenario. Available: `balanced`, `overloaded`, `critical`, `mixed`.

```bash
curl -X POST http://localhost:8000/api/v1/workload/simulate/mixed
```

---

## Core Logic

### 1. Workload Score

```
WorkloadScore = (ActiveTasks × ComplexityWeight) + (DelayedTasks × 2) - (AvailabilityScore / 10)
```

`ComplexityWeight` is derived from the employee's task distribution:

| Complexity | Weight |
|------------|--------|
| Low        | 0.5    |
| Medium     | 1.0    |
| High       | 1.8    |
| Critical   | 3.0    |

Scores are min-max normalised to [0, 100] across the current team.

### 2. Risk Classification

| Risk Score | Level  |
|------------|--------|
| 0 – 29     | Low    |
| 30 – 59    | Medium |
| 60+        | High   |

### 3. Detection Heuristics

| Condition        | Rule                                               |
|------------------|----------------------------------------------------|
| Overloaded       | `risk_score >= 60`                                 |
| Underutilized    | `risk_score < 10` AND `availability >= 70` AND `active_tasks <= 2` |
| Bottleneck       | `delayed_tasks / active_tasks >= 0.4`              |

### 4. Team Health Score (0-100)

Starts at 100 and deducts:
- −15 per high-risk employee
- −5 per medium-risk employee
- −10 per bottleneck
- −5–10 if score variance is high
- +2 bonus per low-risk employee

### 5. Recommendation Strategy

1. **Reassign** — overloaded → most-available employee
2. **Split task** — bottleneck with critical tasks
3. **Delay** — low-priority tasks on bottleneck employees
4. **Redistribute** — high variance even without critical overload
5. **Flag** — overloaded with no available receiver (hiring signal)

---

## Real-Time Architecture

```
Client A ──┐
Client B ──┼── GET /stream ──► asyncio.Queue ──┐
Client C ──┘                                    │
                                                ▼
POST /analyse ──► BalancerService._run_pipeline()
                        │
                        ├── WorkloadMonitor.analyse()
                        ├── RiskAnalyzer.analyse()
                        ├── RedistributionEngine.generate()
                        └── _broadcast(event) ──► all subscriber queues
```

- Each `GET /stream` client gets its own `asyncio.Queue`
- `_broadcast()` is called after every `POST /analyse`
- A background heartbeat task pings every 30 seconds to keep connections alive
- New subscribers immediately receive the last known report (catch-up event)

---

## Optional AI Enhancements

The service layer exposes a `context` field on `WorkloadUpdateRequest` for LLM-powered insights:

```python
# In balancer_service.py — extend _run_pipeline() with:
async def _llm_insights(self, report: BalanceReport, context: str) -> str:
    # Call Claude API with the report + context
    # Return a natural-language narrative
    pass
```

Pre-wired extension points:
- `WorkloadUpdateResponse.ai_insights` — LLM narrative field
- `WorkloadUpdateRequest.context` — free-text context for the LLM
- `Task.tags` — used for embedding-based complexity estimation
- `Employee.past_success_rate` — feeds anomaly detection models

---

## Running Tests

```bash
# Smoke test — runs the full pipeline on all 4 scenarios
python -c "
from app.models.schemas import Employee, Task
from app.balancing.workload_monitor import WorkloadMonitor
from app.balancing.risk_analyzer import RiskAnalyzer
from app.balancing.redistribution_engine import RedistributionEngine
from app.data.sample_data import SAMPLE_SCENARIOS

for name, scenario in SAMPLE_SCENARIOS.items():
    employees = [Employee(**e) for e in scenario['employees']]
    tasks = [Task(**t) for t in scenario['tasks']]
    metrics = WorkloadMonitor().analyse(employees)
    report  = RiskAnalyzer().analyse(metrics)
    actions = RedistributionEngine().generate(report, employees, tasks, metrics)
    print(f'{name:12s} → status={report.status.value:20s} health={report.team_health_score} actions={len(actions)}')
"
```

---

## Design Principles

- **Recommendation-only** — `requires_approval: True` on every action; nothing executes automatically
- **Modular** — each module (monitor, analyser, engine) is independently testable and replaceable
- **Stateless logic** — all three balancing modules are pure functions; state lives only in `BalancerService`
- **Extensible** — add new risk heuristics in `risk_analyzer.py`, new recommendation strategies in `redistribution_engine.py`, without touching routes or services
- **Production-ready** — structured logging, input validation via Pydantic v2, async throughout, CORS configured, health endpoint included
