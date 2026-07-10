---
title: SyncVerse Echo
emoji: 🔊
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Echo — the living memory of SyncVerse

Echo is not a chatbot bolted onto SyncVerse. It's an integrated AI teammate:
the collective intelligence and living memory of every team working on a
project — Frontend, Backend, AI, UI/UX, Security, DevOps, and beyond.

Ask it things like:

- "Why did we choose FastAPI instead of Flask?"
- "Who implemented the Risk Dashboard?"
- "What blockers currently exist between Backend and Frontend?"
- "Summarize everything that happened this week."
- "Should we use WebSockets or Server-Sent Events?"
- "Generate documentation for the Risk APIs."

Echo automatically figures out *how* to answer — by recalling project
memory, giving technical advice, analyzing team coordination, or writing
documentation — and always grounds its answers in what's actually happened
on the project.

---

## How it thinks: four modes, one brain

| Mode | When it's used | What it draws on |
|---|---|---|
| **Memory** | "Why did we choose X?", "Who built Y?" | Semantic search over project memories |
| **Technical Advisor** | "Should we use Redis?", "WebSockets or polling?" | Project context + general engineering knowledge |
| **Project Manager** | "What's blocking Frontend?", "Which teams depend on AI?" | Live task/risk data + blocker memories |
| **Documentation** | "Generate docs for the Risk API" | Architecture, decision, and requirement memories |

Mode selection (`app/services/mode_classifier.py`) uses fast keyword
heuristics first, and only calls the LLM to disambiguate genuinely unclear
phrasing — so most requests are classified instantly and for free.

---

## Architecture

```
app/
  core/            # config (env vars only), database engine, logging
  models/          # SQLAlchemy models: Memory + Project/Task/Risk/Team/
                    # Comment/Documentation/TechnicalDecision/Meeting/
                    # Requirement/ConversationMessage
  schemas/         # Pydantic v2 request/response schemas
  repositories/    # Repository pattern - all DB queries live here
  services/        # Service layer - all business logic lives here
    embedding_service.py      # Gemini embeddings (LangChain)
    vector_store_service.py   # ChromaDB persistent semantic index
    llm_service.py            # Chat completion: Groq primary, Gemini fallback (LangChain)
    mode_classifier.py        # Chooses memory/advisor/pm/docs mode
    memory_service.py         # Writes to Postgres + Chroma, semantic search
    auto_memory_collector.py  # Hooks other modules call to auto-record events
    project_manager_service.py# Blocker/dependency/coordination context
    documentation_service.py  # Architecture/decision context for doc-gen
    summary_service.py        # Weekly summary generation
    echo_service.py           # Orchestrates everything for /echo/chat
  api/routes/      # FastAPI routers (thin - delegate to services)
scripts/
  init_db.py       # Create tables, optionally seed demo memories
```

**Data flow for a memory:** Postgres is the source of truth for every
memory record. Whenever a memory is created, Echo also generates an
embedding (Gemini) and writes it to a per-project ChromaDB collection, so
retrieval stays fast and doesn't leak context between projects. If
embedding fails, the memory is still safely persisted in Postgres and can
be re-indexed later.

**Automatic memory collection:** other SyncVerse modules (task board, risk
register, sprint planner, requirements, meeting notes) call the small,
explicit hooks in `AutoMemoryCollector` — `task_completed()`,
`risk_added()`, `blocker_reported()`, `technical_decision_created()`, etc.
— whenever something noteworthy happens, so project memory builds itself
instead of requiring manual entry.

---

## API

All endpoints are mounted under `/echo` by default (`API_PREFIX` env var).

### `POST /echo/chat` — talk to Echo
```json
// Request
{ "project_id": "uuid", "user_id": "string", "message": "Why did we choose FastAPI?" }

// Response
{
  "response": "...",
  "sources": [{ "memory_id": "...", "title": "...", "memory_type": "decision", "team_name": "Backend", "relevance_score": 0.97 }],
  "mode": "memory",
  "confidence": 0.91
}
```

### `POST /echo/memory` — manually record a memory
Most memories should be created automatically via `AutoMemoryCollector`,
but this endpoint exists for manual entry, imports, and integrations.

### `GET /echo/project/{project_id}/timeline` — chronological memories
Supports `limit`, `offset`, `memory_type`, `team_name` filters.

### `GET /echo/summary/week?project_id=...` — weekly summary
LLM-generated summary grouped by theme (decisions, progress, risks/blockers,
meetings), plus the highlighted memories behind it.

### `GET /echo/health` — health check
Reports database, vector store, and LLM-credential status.

Full interactive docs (OpenAPI) are always available at `/docs`.

---

## Running locally

### Option A — bare metal, zero config (fastest)
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # set GROQ_API_KEY (and GOOGLE_API_KEY for embeddings + fallback); leave DATABASE_URL empty for SQLite

python scripts/init_db.py --seed   # create tables + demo memories (SQLite file under ./data)
uvicorn app.main:app --reload --port 8000
```
With no `DATABASE_URL` set, Echo automatically uses a local SQLite file
(`SQLITE_PATH`, default `/data/echo.db` — override it to something like
`./data/echo.db` for local runs outside a container). No database server
required.

### Option B — Docker Compose with PostgreSQL
Use this when you want to develop against Postgres (closer to a
production setup):
```bash
cp .env.example .env
# edit .env and set GOOGLE_API_KEY at minimum
docker compose up --build
```
`docker-compose.yml` sets `DATABASE_URL` to point at the bundled Postgres
service automatically. The app is at `http://localhost:7860`, docs at
`http://localhost:7860/docs`.

> Chat completions use Groq by default (`GROQ_API_KEY`), with Gemini as an
> automatic fallback (`GOOGLE_API_KEY`) if Groq times out, hits a rate
> limit/quota error, or has a transient API/network failure. Embeddings
> always use Gemini, so `GOOGLE_API_KEY` is still needed for real memory
> retrieval either way. Set `CHAT_PROVIDER=gemini` to skip Groq entirely.
> Without any chat provider key, Echo still boots and stores/retrieves
> memories normally, but chat responses and embeddings fall back to a
> degraded local mode (deterministic hash embeddings, placeholder chat
> replies) — useful for local dev and CI, not for real answers.

---

## Deploying to Hugging Face Spaces

Echo is designed for a zero-config deploy: if you don't provide a
`DATABASE_URL`, it automatically falls back to a local SQLite database at
`/data/echo.db`, so no external database is required to get it running.

1. **Create a Space** → SDK: **Docker**.
2. **Push this repository** to the Space's git remote (the `Dockerfile` at
   the repo root is picked up automatically).
3. **Add secrets** under Space Settings → Repository secrets:
   - `GROQ_API_KEY` — your Groq API key (primary chat provider)
   - `GOOGLE_API_KEY` — your Gemini API key (required for embeddings, and
     used as the automatic chat fallback if Groq fails; the app still
     boots without either key, in a degraded fallback mode)
4. **Enable persistent storage** on the Space (Settings → Persistent
   storage). This keeps `/data` — both the SQLite database and the
   ChromaDB vector index — intact across restarts. Without it, data is
   wiped whenever the Space sleeps or restarts.
5. On first boot the app automatically creates all tables (`init_db()`
   runs in the FastAPI `lifespan` hook) — no manual migration step needed.
6. Once the Space is running, verify with:
   ```bash
   curl https://<your-space>.hf.space/echo/health
   ```
   The response includes `"database_backend": "sqlite"` or
   `"postgresql"` so you can confirm which mode is active.

### Optional: use PostgreSQL instead
For heavier production use, set `DATABASE_URL` as an additional secret to
a managed Postgres connection string (HF Spaces don't host Postgres
themselves — use something like [Neon](https://neon.tech) or
[Supabase](https://supabase.com)):
```
DATABASE_URL=postgresql+psycopg2://user:pass@host/dbname
```
When this is set, Echo uses it instead of SQLite automatically — no code
changes needed either way.

---

## Environment variables

See `.env.example` for the full list. Nothing is ever hardcoded — every
credential, model name, and tuning parameter comes from the environment.

---

## Troubleshooting

**Chat replies with "no available quota" / logs show `429 ResourceExhausted`, `limit: 0`**
This means the configured `GOOGLE_API_KEY`'s project has zero free-tier
quota for whatever model `GEMINI_CHAT_MODEL` points to — usually because
it's an older model that Google no longer grants free quota to on
unverified projects, not because you've actually used up a quota. Fixes,
easiest first:
1. Check your project's live per-model limits at
   [aistudio.google.com/rate-limit](https://aistudio.google.com/rate-limit)
   and set `GEMINI_CHAT_MODEL` to a model shown with non-zero free quota
   (the default, `gemini-2.5-flash`, currently has one - but Google
   changes this over time, so re-check if it happens again).
2. Link a billing account on the project in AI Studio. This moves you out
   of the restrictive zero-quota "Free Tier" bucket into the standard
   quota system, without necessarily costing anything if you stay under
   the free allowance.

Either way, no code change is needed — just update the `GEMINI_CHAT_MODEL`
secret/env var and restart. The app also fails fast on quota errors
(`max_retries=1`) instead of hanging the request for tens of seconds.

**Logs show `Failed to send telemetry event ... capture() takes 1 positional argument but 3 were given`**
Harmless - it's ChromaDB trying (and failing) to send anonymous usage
telemetry due to a version mismatch with a newer `posthog` package. Fixed
by the pinned `posthog==2.4.2` in `requirements.txt`; if you see this
again, check that pin hasn't been dropped or overridden.

---

## Extending Echo

- **New entity types** (e.g. "epics", "incidents"): add a model under
  `app/models/`, a repository under `app/repositories/`, and register it in
  `app/models/__init__.py` + `app/core/database.py::init_db`.
- **New automatic memory events**: add a method to `AutoMemoryCollector`
  and call it from wherever the event originates in the wider SyncVerse
  platform.
- **New Echo modes**: add a pattern set + enum value in
  `mode_classifier.py`, a system prompt in `echo_service.py`, and (if the
  mode needs structured context beyond semantic search) a small service
  like `project_manager_service.py`.
