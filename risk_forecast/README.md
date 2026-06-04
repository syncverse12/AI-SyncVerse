---
title: Risk Forecast
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 8000
---

# SyncVerse AI Risk Intelligence Engine

> **"An AI operational nervous system for your company."**
> Proactively detects, predicts, explains, and reduces project risks before failure happens.

---

## What It Does

The Risk Intelligence Engine is **not a dashboard**. It is a proactive AI operational layer that:

1. **Before a project starts** — analyzes requirements, team capacity, skills, timeline, and budget to forecast risks with probability scores and specific explanations.
2. **During execution** — continuously monitors live metrics (GitHub activity, sprint velocity, PR bottlenecks, sentiment, client alignment) and dynamically updates the risk picture.
3. **Autonomously** — fires structured alerts with AI-generated insights, root cause explanations, and concrete mitigation actions.
4. **Learns** — stores all projects, incidents, and retrospectives in a vector database and retrieves similar historical cases to ground every prediction in real company memory.

---

## Architecture

```
app/
├── api/routes/          # FastAPI endpoints (risk_routes.py)
├── services/            # Business logic orchestration (risk_service.py)
├── ai/
│   ├── orchestrators/   # LLM client — OpenAI / Gemini (ai_orchestrator.py)
│   └── prompts/         # All prompts centralized (risk_prompts.py)
├── ml/models/           # XGBoost / LightGBM predictors (predictor.py)
├── rag/                 # Qdrant vector retrieval (rag_service.py)
├── realtime/            # WebSocket + Redis Pub/Sub (ws_manager.py)
├── alerts/              # Autonomous alert engine (alert_engine.py)
├── scoring/             # Rule-based + composite scoring (risk_engine.py)
├── workers/             # Celery background tasks (tasks.py)
├── models/              # Pydantic schemas + ORM models
├── repositories/        # Database access layer
└── core/                # Config, logging, DB connections
```

---

## Risk Score Formula

```
risk_score = (
    deadline_risk        × 0.25  +
    workload_risk        × 0.20  +
    skill_gap_risk       × 0.20  +
    deployment_failure   × 0.15  +
    client_alignment     × 0.10  +
    inactivity_risk      × 0.10
)
× ML_adjustment × AI_calibration
```

All weights are configurable via environment variables — no code changes needed.

---

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your API keys

# 2. Start infrastructure
docker-compose up -d postgres redis qdrant

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run database migrations
alembic upgrade head

# 5. Start the API server
uvicorn app.main:app --reload

# 6. Start Celery worker (separate terminal)
celery -A app.workers.tasks.celery_app worker --loglevel=info

# 7. Start Celery Beat scheduler (separate terminal)
celery -A app.workers.tasks.celery_app beat --loglevel=info
```

Or run everything with Docker:
```bash
docker-compose up
```

---

## API Reference

### Pre-Project Risk Analysis
```
POST /api/v1/risk/analyze-project
```

### Live Risk Update
```
POST /api/v1/risk/live-update
```

### Get Latest Report
```
GET /api/v1/risk/project/{project_id}
```

### Risk History (for charts)
```
GET /api/v1/risk/history/{project_id}?limit=30
```

### Alerts
```
GET  /api/v1/risk/alerts?project_id=...&severity=HIGH
POST /api/v1/risk/alerts/acknowledge
```

### WebSocket (Realtime)
```
WS /api/v1/risk/ws/{project_id}
```

**Events received:**
- `snapshot` — initial state on connect
- `risk_update` — new risk scores computed
- `alert` — alert fired for this project
- `heartbeat` — keep-alive every 30s

---

## Example API Request

### Pre-Project Analysis
```json
POST /api/v1/risk/analyze-project
{
  "project_name": "E-Commerce Platform Rebuild",
  "description": "Full replatform from monolith to microservices",
  "client_name": "RetailCo",
  "start_date": "2025-06-01T00:00:00Z",
  "deadline": "2025-09-30T00:00:00Z",
  "estimated_hours": 2400,
  "budget_usd": 180000,
  "team": [
    { "name": "Alice", "role": "Backend", "skills": ["Python", "FastAPI", "PostgreSQL"], "current_workload_pct": 80, "seniority_years": 4 },
    { "name": "Bob", "role": "Frontend", "skills": ["React", "TypeScript"], "current_workload_pct": 60, "seniority_years": 2 }
  ],
  "tech_stack": {
    "languages": ["Python", "TypeScript"],
    "frameworks": ["FastAPI", "React"],
    "infrastructure": ["AWS", "Docker", "Kubernetes"],
    "third_party_apis": ["Stripe", "SendGrid", "Twilio"]
  },
  "required_skills": ["Python", "Kubernetes", "Redis", "GraphQL"],
  "requirement_completeness_pct": 65,
  "dependencies_count": 12,
  "client_responsiveness": 6.0
}
```

### Example Risk Report Response
```json
{
  "report_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "project_id": "...",
  "report_type": "pre_project",
  "scores": {
    "overall": 0.71,
    "severity": "HIGH",
    "confidence": 0.92,
    "categories": [
      { "category": "technical", "score": 0.75, "severity": "HIGH", "contributing_factors": ["Missing skills: Kubernetes, GraphQL", "12 external dependencies"] },
      { "category": "human",     "score": 0.68, "severity": "HIGH", "contributing_factors": ["Alice at 80% capacity before project starts"] },
      { "category": "delivery",  "score": 0.62, "severity": "HIGH", "contributing_factors": ["Requirements only 65% complete"] }
    ]
  },
  "delay_probability": 0.74,
  "budget_overrun_probability": 0.58,
  "delivery_confidence": 0.31,
  "burnout_probability": 0.67,
  "executive_summary": "This project carries HIGH risk primarily due to critical skill gaps in Kubernetes and GraphQL, a pre-loaded team (Alice at 80% capacity), and requirements that are only 65% complete — creating substantial scope creep exposure across a 4-month timeline.",
  "root_causes": [
    "Team lacks Kubernetes and GraphQL expertise required for the microservices architecture",
    "Requirement incompleteness (65%) will drive rework and scope creep in sprints 3-5",
    "Alice's 80% pre-existing workload creates a single point of failure on the backend"
  ],
  "predicted_consequences": [
    "Kubernetes learning curve will add 3-4 weeks to infrastructure setup",
    "Incomplete requirements will likely extend the timeline by 4-6 weeks beyond the September deadline",
    "Backend bottleneck risk increases if Alice takes any leave during critical delivery phase"
  ],
  "mitigation_plan": [
    { "priority": 1, "action": "Hire or contract a Kubernetes specialist for the first 6 weeks", "owner_role": "Engineering Manager", "estimated_impact": "Reduces infrastructure delay risk from 74% to 35%", "timeframe_days": 14 },
    { "priority": 2, "action": "Run a 2-week requirements clarification sprint before coding begins", "owner_role": "Product Manager", "estimated_impact": "Increases requirement completeness to 90%+", "timeframe_days": 7 },
    { "priority": 3, "action": "Reduce Alice's current project allocation to 50% before start date", "owner_role": "Project Manager", "estimated_impact": "Eliminates team overload risk", "timeframe_days": 14 }
  ]
}
```

### Example Alert Payload
```json
{
  "alert_id": "a3f2d1e0-...",
  "project_id": "...",
  "fired_at": "2025-07-15T14:32:00Z",
  "severity": "HIGH",
  "risk_category": "human",
  "title": "HIGH Human Risk: 78% (+23%)",
  "message": "Human risk increased from 55% to 78% (+23%). Contributing factors: Average overtime at 18h/week — burnout imminent; 6 task reassignments this sprint.",
  "root_cause": "Average overtime at 18h/week — burnout imminent; 6 task reassignments — instability signal",
  "ai_insight": "The frontend team has averaged 18 overtime hours per week for 3 consecutive sprints, pushing burnout probability above 80%. The pattern of 6 task reassignments suggests either unclear ownership or hidden blockers. Without intervention in the next 72 hours, expect a 2-3 week productivity crash.",
  "recommended_action": "Reduce workload, redistribute tasks, and assess burnout indicators.",
  "previous_risk_score": 0.55,
  "current_risk_score": 0.78,
  "delta": 0.23,
  "escalation_level": 2,
  "notify_roles": ["project_manager", "engineering_lead", "product_owner"]
}
```

---

## Configuration

All risk weights and alert thresholds are configurable via `.env`:

```bash
# Adjust risk scoring weights
RISK_WEIGHT_DEADLINE=0.25
RISK_WEIGHT_WORKLOAD=0.20
RISK_WEIGHT_SKILL_GAP=0.20

# Adjust alert thresholds
ALERT_THRESHOLD_HIGH=0.70
ALERT_THRESHOLD_CRITICAL=0.85
ALERT_COOLDOWN_SECONDS=900
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| AI Reasoning | OpenAI GPT-4o / Google Gemini |
| Vector Memory | Qdrant |
| ML Models | XGBoost + LightGBM |
| Database | PostgreSQL (async) |
| Cache + Pub/Sub | Redis |
| Task Queue | Celery + Redis |
| Realtime | WebSockets |
| Logging | Structlog (JSON) |
| ORM | SQLAlchemy 2.0 (async) |

---

## Extending the System

- **Add a new risk category**: Add to `RiskCategory` enum, implement scorer method in `risk_engine.py`, update weights in `.env`
- **Swap the AI provider**: Set `AI_PROVIDER=gemini` in `.env` — no code changes
- **Add an ML model**: Drop a `.ubj` or `.txt` file in `app/ml/models/saved_models/` and register in `predictor.py`
- **Add a new alert channel** (Slack, email, PagerDuty): Subscribe to the Redis Pub/Sub channel `alerts:{project_id}` in any service

---

*Built for SyncVerse — the AI-powered project intelligence platform.*
