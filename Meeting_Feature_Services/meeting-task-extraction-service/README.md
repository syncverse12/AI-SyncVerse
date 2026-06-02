# Meeting Task Extraction Service

A stateless FastAPI microservice that extracts actionable tasks from meeting transcripts using Groq LLM (llama-3.3-70b) and optional spaCy NER for assignee detection.

---

## Features

- Extracts tasks, assignees, deadlines, priorities, and categories
- Handles multi-speaker transcripts in English or Arabic
- Optional spaCy NER for supplementing attendee detection
- Splits long transcripts into chunks automatically
- Deduplicates tasks across chunks
- Fully stateless — no database, no Redis, no file I/O

---

## API

### `GET /health`
```json
{ "status": "healthy", "service": "Meeting Task Extraction Service", "version": "1.0.0" }
```

### `POST /extract-tasks`

**Request:**
```json
{
  "meeting_id": 15,
  "transcript": "Ahmed said he will deploy the backend by Friday. Marwa needs to finish the dashboard UI.",
  "attendees": ["Ahmed Mohamed", "Marwa Hassan", "Sara Ali"],
  "meeting_date": "2025-01-13"
}
```

**Response:**
```json
{
  "meeting_id": 15,
  "tasks_count": 2,
  "tasks": [
    {
      "title": "Deploy backend",
      "description": null,
      "assignee": "Ahmed Mohamed",
      "deadline": "2025-01-17",
      "priority": "HIGH",
      "category": "deployment",
      "estimated_hours": null,
      "source_quote": "Ahmed said he will deploy the backend by Friday.",
      "confidence": 0.95
    },
    {
      "title": "Finish dashboard UI",
      "description": null,
      "assignee": "Marwa Hassan",
      "deadline": null,
      "priority": "MEDIUM",
      "category": "design",
      "estimated_hours": null,
      "source_quote": "Marwa needs to finish the dashboard UI.",
      "confidence": 0.92
    }
  ],
  "processing_notes": []
}
```

---

## Local Development

### 1. Clone and set up environment
```bash
git clone <repo-url>
cd meeting-task-extraction-service
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

Open: http://localhost:7860/docs

---

## Docker

### Build
```bash
docker build -t meeting-task-extraction-service .
```

### Run
```bash
docker run -p 7860:7860 \
  -e GROQ_API_KEY=your_key_here \
  meeting-task-extraction-service
```

### Test
```bash
curl -X POST http://localhost:7860/extract-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_id": 1,
    "transcript": "Ahmed will deploy the backend by Friday. Marwa should update the docs.",
    "attendees": ["Ahmed Mohamed", "Marwa Hassan"],
    "meeting_date": "2025-01-13"
  }'
```

---

## Hugging Face Spaces Deployment

### Step 1: Create a new Space
1. Go to https://huggingface.co/spaces
2. Click **Create new Space**
3. Choose **Docker** as the SDK
4. Set visibility to **Public** or **Private**

### Step 2: Add your secret
1. In your Space settings → **Variables and secrets**
2. Add secret: `GROQ_API_KEY` = your key

### Step 3: Push your code
```bash
git init
git remote add space https://huggingface.co/spaces/<your-username>/meeting-task-extraction
git add .
git commit -m "Initial deployment"
git push space main
```

The Space will build the Docker image and expose your API at:
`https://<your-username>-meeting-task-extraction.hf.space`

### Step 4: Test the deployed service
```bash
curl -X POST https://<your-username>-meeting-task-extraction.hf.space/extract-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_id": 99,
    "transcript": "Sara will prepare the test report by Wednesday.",
    "attendees": ["Sara Ali"],
    "meeting_date": "2025-01-13"
  }'
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ | — | Your Groq API key |
| `GROQ_MODEL` | ❌ | `llama-3.3-70b-versatile` | Groq model name |
| `GROQ_TEMPERATURE` | ❌ | `0.1` | LLM temperature (lower = more deterministic) |
| `GROQ_MAX_TOKENS` | ❌ | `4096` | Max tokens in LLM response |
| `USE_SPACY_NER` | ❌ | `true` | Use spaCy NER for person detection |
| `ENVIRONMENT` | ❌ | `production` | Environment label |

---

## Removed Dependencies (vs monolith)

The following were present in the original monolith and have been **completely removed**:

- ❌ SQLAlchemy / asyncpg / PostgreSQL
- ❌ Redis / aioredis
- ❌ WebSockets / FastAPI WebSocket
- ❌ JWT / authentication middleware
- ❌ Alembic migrations
- ❌ AssemblyAI
- ❌ LangChain
- ❌ Meeting pipeline orchestration
- ❌ Database models (Employee, Meeting, Transcript, etc.)
