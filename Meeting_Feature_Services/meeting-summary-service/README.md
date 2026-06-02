# Meeting Summary Service

A stateless FastAPI microservice that generates structured meeting summaries from transcripts using Groq LLM (llama-3.3-70b). Handles long transcripts automatically via chunking and merging.

---

## Features

- Generates executive overview, key points, decisions, risks, next steps, and action items
- Handles long transcripts automatically (chunk → summarize → merge)
- Deduplicates overlapping points across chunks
- Supports English and Arabic output
- Fully stateless — no database, no Redis, no file I/O

---

## API

### `GET /health`
```json
{ "status": "healthy", "service": "Meeting Summary Service", "version": "1.0.0" }
```

### `POST /generate-summary`

**Request:**
```json
{
  "meeting_id": 15,
  "transcript": "Ahmed said we decided to use PostgreSQL. Marwa will prepare the migration scripts by Thursday. Sara raised a concern about downtime during migration. We agreed to run migration on Sunday night.",
  "meeting_title": "Database Migration Planning",
  "attendees": ["Ahmed Mohamed", "Marwa Hassan", "Sara Ali"],
  "language": "en"
}
```

**Response:**
```json
{
  "meeting_id": 15,
  "meeting_title": "Database Migration Planning",
  "summary": "The team planned the upcoming PostgreSQL migration. Key decisions were made around timing and ownership, with migration scheduled for Sunday night to minimize impact.",
  "key_points": [
    "Database migration to PostgreSQL was confirmed",
    "Migration scheduled for Sunday night to reduce downtime",
    "Marwa will prepare the migration scripts"
  ],
  "decisions": [
    "Decided to use PostgreSQL as the new database",
    "Migration to run on Sunday night"
  ],
  "risks": [
    "Potential downtime during migration raised by Sara"
  ],
  "next_steps": [
    "Monitor migration on Sunday",
    "Prepare rollback plan"
  ],
  "action_items": [
    {
      "task": "Prepare migration scripts",
      "owner": "Marwa Hassan",
      "deadline": "2025-01-16"
    }
  ],
  "full_markdown": "# Database Migration Planning\n\n## Summary\n..."
}
```

---

## Local Development

### 1. Clone and set up
```bash
git clone <repo-url>
cd meeting-summary-service
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run
```bash
uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

Open: http://localhost:7860/docs

---

## Docker

### Build
```bash
docker build -t meeting-summary-service .
```

### Run
```bash
docker run -p 7860:7860 \
  -e GROQ_API_KEY=your_key_here \
  meeting-summary-service
```

### Test
```bash
curl -X POST http://localhost:7860/generate-summary \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_id": 1,
    "transcript": "We decided to use PostgreSQL. Marwa will prepare migration scripts by Thursday.",
    "meeting_title": "DB Planning",
    "attendees": ["Marwa Hassan", "Ahmed Mohamed"],
    "language": "en"
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
git remote add space https://huggingface.co/spaces/<your-username>/meeting-summary-service
git add .
git commit -m "Initial deployment"
git push space main
```

Your API will be live at:
`https://<your-username>-meeting-summary-service.hf.space`

### Step 4: Test deployed service
```bash
curl -X POST https://<your-username>-meeting-summary-service.hf.space/generate-summary \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_id": 42,
    "transcript": "We agreed to launch the product on March 1st.",
    "meeting_title": "Launch Planning",
    "attendees": ["Ahmed", "Sara"],
    "language": "en"
  }'
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ | — | Your Groq API key |
| `GROQ_MODEL` | ❌ | `llama-3.3-70b-versatile` | Groq model name |
| `GROQ_TEMPERATURE` | ❌ | `0.2` | LLM temperature |
| `GROQ_MAX_TOKENS` | ❌ | `4096` | Max tokens in LLM response |
| `MAX_TRANSCRIPT_CHARS` | ❌ | `14000` | Characters per chunk before splitting |
| `ENVIRONMENT` | ❌ | `production` | Environment label |

---

## Removed Dependencies (vs monolith)

- ❌ SQLAlchemy / asyncpg / PostgreSQL
- ❌ Redis / aioredis
- ❌ WebSockets
- ❌ JWT / authentication
- ❌ Alembic migrations
- ❌ AssemblyAI
- ❌ LangChain
- ❌ spaCy / NER
- ❌ Meeting pipeline orchestration
- ❌ All ORM models
