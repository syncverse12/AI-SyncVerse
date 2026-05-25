# 🚀 Intelligent Project Management System

> Enterprise-grade AI-powered project evaluation platform built on  
> **FastAPI · Qdrant · OpenAI Embeddings · GPT-4o Judge**

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI Layer                        │
│   POST /project/{id}/health                                 │
│   POST /project/{id}/alignment                              │
│   POST /project/{id}/ai-judge                               │
│   POST /project/{id}/evaluate   ← full pipeline             │
└──────────┬──────────────────────────────────────────────────┘
           │
    ┌──────▼──────────────────────────────────────┐
    │         Evaluation Orchestrator              │
    └──┬───────────┬──────────────┬───────────────┘
       │           │              │
  ┌────▼────┐ ┌────▼────┐ ┌──────▼──────────────┐
  │ Health  │ │Alignment│ │   AI Judge Layer      │
  │ Score   │ │ Score   │ │  RAG → LLM → Critic  │
  │ Layer 1 │ │ Layer 2 │ │       Layer 3         │
  └─────────┘ └────┬────┘ └──────────────────────┘
                   │
           ┌───────▼──────┐
           │    Qdrant     │
           │ Vector Store  │
           │ requirements  │
           │ tasks         │
           │ deliverables  │
           │ notes         │
           └───────────────┘
```

---

## Three Intelligence Layers

### 📊 Layer 1 — Project Health Score

Pure execution metrics (no LLM, no I/O):

| Component | Weight | Description |
|---|---|---|
| Goal Progress | 40% | Weighted completion across all project goals |
| Completion Rate | 25% | Completed tasks / total tasks |
| Efficiency Score | 20% | estimated_hours / actual_hours ratio |
| Delay Penalty | 15% | `Σ(delay_days × priority_weight)` normalised |

```
Health Score = 0.40 × GoalProgress
             + 0.25 × CompletionRate
             + 0.20 × EfficiencyScore
             - 0.15 × DelayScore     (normalised 0–100)
```

**Priority multipliers for delays:**
- `critical` → ×3  |  `high` → ×2  |  `medium` → ×1  |  `low` → ×0.5

---

### 🧠 Layer 2 — Client Alignment Score

Semantic matching between requirements and task deliverables using Qdrant:

1. **Embed** every requirement description
2. **Query** Qdrant `tasks_vectors` collection with cosine similarity
3. **Average** top-k similarity scores per requirement
4. **Weight-average** across all requirements

```
Alignment Score = Σ(requirement_weight × avg_similarity) / Σ(weights)  ×  100
```

**Automatic alerts triggered:**
| Condition | Severity |
|---|---|
| alignment < 50% | 🔴 Critical misalignment |
| 50% ≤ alignment < 75% | 🟡 Risk |
| No tasks for requirement | 🔴 Drift Detected |
| Tasks with no requirement | 🟡 Orphan Work |

---

### 🔥 Layer 3 — AI Judge (RAG + LLM + Critic)

**Step 1 — Composite Query Construction**
Build a query embedding from weak-points:
- Low-alignment requirements
- Delayed task titles
- Underperforming goals

**Step 2 — Qdrant RAG Retrieval**
Retrieve top-k from all collections simultaneously:
```
requirements_vectors  →  relevant requirements
tasks_vectors         →  relevant tasks
deliverables_vectors  →  relevant deliverables
```

**Step 3 — LLM Judge (GPT-4o)**
Evaluates across 5 dimensions:
1. Requirement Coverage
2. Semantic Completeness
3. Execution Quality
4. Risk Detection (bottlenecks, overload, instability)
5. Consistency Check (requirements ↔ tasks ↔ goals ↔ deliverables)

**Step 4 — Critic Loop (second LLM)**
A second LLM validates the first judgment:
- Checks for hallucinated problems
- Validates score fairness
- Can adjust `ai_judge_score` and `confidence`

**Output:**
```json
{
  "ai_judge_score": 72,
  "confidence": 0.85,
  "adjusted_health_score": 68,
  "risk_level": "medium",
  "summary": "Project execution is solid but inventory service is critically delayed...",
  "key_issues": ["Inventory service 12 days past deadline", "Recommendation engine not started"],
  "recommendations": ["Prioritise inventory task", "Assign ML engineer to r3"],
  "detected_gaps": ["r4 requirement has zero deliverable coverage"],
  "critic_validated": true,
  "critic_notes": "Judgment is fair and evidence-based."
}
```

---

## Bonus Features

### 🔍 Drift Detection
- Compares requirement intent vs. task coverage
- Flags `semantic_drift` when alignment < 65%
- Flags `no_coverage` for requirements with zero matching tasks
- Flags `orphan_tasks` for work with no requirement link

### 📈 Predictive Risk Forecast
- Projects misalignment, delay, and failure risk over next N days
- Considers upcoming deadlines, critical task count, and current trajectory
- Returns `low | medium | high | critical` risk level + driver explanations

---

## Project Structure

```
intelligent_pm/
├── app/
│   ├── main.py                          # FastAPI app factory + lifespan
│   ├── core/
│   │   ├── config.py                    # Pydantic Settings (env-based)
│   │   └── logging.py                   # Structured JSON logging
│   ├── models/
│   │   └── domain.py                    # All domain models + enums
│   ├── schemas/
│   │   └── schemas.py                   # API request/response schemas
│   ├── routers/
│   │   ├── health_router.py             # POST /project/{id}/health
│   │   ├── alignment_router.py          # POST /project/{id}/alignment
│   │   └── ai_judge_router.py           # POST /project/{id}/ai-judge + /evaluate
│   ├── services/
│   │   ├── health_service.py            # Layer 1 — pure computation
│   │   ├── alignment_service.py         # Layer 2 — Qdrant semantic search
│   │   ├── embedding_service.py         # OpenAI embeddings + Redis cache
│   │   ├── qdrant_service.py            # Orchestrates embed → index
│   │   ├── rag_service.py               # RAG context assembly
│   │   ├── ai_judge_service.py          # LLM judge + critic loop
│   │   ├── drift_service.py             # Drift detection + risk forecast
│   │   └── evaluation_orchestrator.py   # Full pipeline orchestrator
│   └── vector_store/
│       ├── qdrant_client.py             # Singleton client + bootstrap
│       ├── indexing.py                  # Upsert documents → Qdrant
│       └── retrieval.py                 # Semantic search helpers
├── tests/
│   └── test_evaluation.py               # 16 unit tests (no external I/O)
├── sample_project.json                  # Example request payload
├── docker-compose.yml                   # Qdrant + Redis + API
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Quick Start

### 1. Clone & Configure
```bash
cp .env.example .env
# Edit .env: set OPENAI_API_KEY
```

### 2. Start Infrastructure
```bash
docker-compose up -d qdrant redis
```

### 3. Run the API
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Or fully containerised:
```bash
docker-compose up
```

### 4. Run Tests
```bash
pytest tests/ -v
```

---

## API Reference

All endpoints accept the full `Project` object in the request body.

### `POST /project/{id}/health`
Layer 1 — Execution health score. No Qdrant needed.
```bash
curl -X POST http://localhost:8000/project/proj-001/health \
  -H "Content-Type: application/json" \
  -d @sample_project.json
```

### `POST /project/{id}/alignment`
Layer 2 — Semantic alignment against requirements.
```bash
curl -X POST "http://localhost:8000/project/proj-001/alignment?reindex=true" \
  -H "Content-Type: application/json" \
  -d @sample_project.json
```

### `POST /project/{id}/ai-judge`
Layer 3 — RAG-grounded LLM evaluation.
```bash
curl -X POST "http://localhost:8000/project/proj-001/ai-judge?run_critic=true" \
  -H "Content-Type: application/json" \
  -d @sample_project.json
```

### `POST /project/{id}/evaluate`
**Full pipeline** — all layers + drift + forecast in one call.
```bash
curl -X POST "http://localhost:8000/project/proj-001/evaluate?reindex=true&forecast_days=14" \
  -H "Content-Type: application/json" \
  -d @sample_project.json
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | **Required.** OpenAI API key |
| `OPENAI_LLM_MODEL` | `gpt-4o` | LLM model for judging |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant HTTP port |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for embedding cache |
| `EMBEDDING_CACHE_TTL` | `86400` | Cache TTL in seconds |
| `RAG_TOP_K` | `8` | Top-k results per Qdrant query |
| `RAG_SCORE_THRESHOLD` | `0.55` | Minimum similarity threshold |
| `HEALTH_WEIGHT_GOAL_PROGRESS` | `0.40` | Tunable scoring weight |
| `HEALTH_WEIGHT_COMPLETION_RATE` | `0.25` | Tunable scoring weight |
| `HEALTH_WEIGHT_EFFICIENCY` | `0.20` | Tunable scoring weight |
| `HEALTH_WEIGHT_DELAY` | `0.15` | Tunable scoring weight |

---

## Key Design Decisions

| Principle | Implementation |
|---|---|
| **Qdrant only** | No other vector DB used anywhere |
| **RAG before LLM** | `rag_service.py` always runs before `ai_judge_service.py` |
| **Explainable scores** | Every score has a `score_breakdown` dict |
| **Cached embeddings** | Redis with SHA-256 keying, 24h TTL |
| **Idempotent indexing** | UUID5 deterministic IDs — safe to re-run |
| **Modular services** | Each layer is independently testable |
| **Critic loop** | Second LLM validates first judgment |
| **Real-time ready** | Any endpoint accepts `reindex=true` for live updates |
