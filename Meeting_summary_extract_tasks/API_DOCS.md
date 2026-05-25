# AI Meeting Intelligence System — API Documentation

## Base URL
```
http://localhost:8000
```
Interactive docs: `http://localhost:8000/docs`

---

## Authentication

All protected endpoints require a JWT Bearer token in the `Authorization` header.

### POST /auth/register
Register a new employee.
```json
Request:
{ "name": "Ahmed Mohamed", "email": "ahmed@co.com", "password": "secret123",
  "department": "Engineering", "role": "Backend Engineer" }

Response 201:
{ "id": "uuid", "name": "Ahmed Mohamed", "email": "ahmed@co.com", ... }
```

### POST /auth/login
```json
Request: { "email": "ahmed@co.com", "password": "secret123" }
Response: { "access_token": "jwt...", "token_type": "bearer" }
```

### GET /auth/me
Returns the current authenticated employee.

---

## Meeting Management

### POST /meeting/start
Create and start a new meeting. Host is auto-added as attendee.
```json
Request:
{
  "title": "Q2 Sprint Planning",
  "language": "mixed",
  "attendee_ids": ["uuid-marwa", "uuid-sara"]
}

Response 201:
{
  "id": "meeting-uuid",
  "title": "Q2 Sprint Planning",
  "host_id": "uuid-ahmed",
  "status": "PENDING",
  "attendees": [...],
  "started_at": "2025-01-15T10:00:00"
}
```

### POST /meeting/end
Signal end of meeting. Triggers the full post-meeting pipeline asynchronously.
```json
Request: { "meeting_id": "meeting-uuid" }
Response 202: { "status": "accepted", "meeting_id": "...", "message": "Pipeline started" }
```

### GET /meeting/{meeting_id}
Get meeting details.

### GET /meeting/
List host's meetings.

### GET /meeting/{meeting_id}/transcript
Get full transcript in English and Arabic.
```json
{
  "full_text_en": "Ahmed said we need to deploy...",
  "full_text_ar": "قال أحمد إننا بحاجة إلى النشر...",
  "utterances": [
    { "speaker": "Speaker A", "text": "...", "start_ms": 0, "end_ms": 3200 }
  ]
}
```

### GET /meeting/{meeting_id}/summary
Get meeting summary. Available to ALL attendees.
```json
{
  "overview": "The team discussed Q2 sprint goals...",
  "key_points": ["Point 1", "Point 2"],
  "decisions": ["Decided to use PostgreSQL"],
  "blockers": ["Waiting on API credentials"],
  "next_steps": ["Ahmed deploys backend by Friday"],
  "action_items": [
    { "task": "Deploy backend", "owner": "Ahmed", "deadline": "2025-01-17" }
  ],
  "full_markdown": "# Meeting Summary\n\n## Overview\n..."
}
```

### GET /meeting/{meeting_id}/tasks
Get all tasks for a meeting (host only).

---

## Employee Dashboard

### GET /employee/{id}/tasks
Get tasks assigned to a specific employee.
Query params: `status=TODO|IN_PROGRESS|DONE|BLOCKED`, `meeting_id=uuid`

```json
[
  {
    "id": "task-uuid",
    "title": "Deploy backend service",
    "priority": "HIGH",
    "status": "TODO",
    "deadline": "2025-01-17T00:00:00",
    "meeting_id": "meeting-uuid",
    "assignee_raw": "Ahmed"
  }
]
```

### GET /employee/me/tasks
Get current employee's tasks.

### PATCH /employee/me/tasks/{task_id}
Update task status.
```json
Request: { "status": "IN_PROGRESS", "priority": "URGENT" }
```

### GET /employee/me/meetings
List meetings the employee attended.

---

## WebSocket: Audio Streaming

```
WS ws://localhost:8000/ws/meeting/stream?meeting_id=UUID&employee_id=UUID
```

### Client → Server
- **Binary frames**: Raw 16kHz 16-bit mono PCM audio chunks
- **Text JSON**: `{"action": "end_stream"}` to signal meeting end
- **Text JSON**: `{"action": "ping"}` keepalive

### Server → Client (JSON events)
```json
{ "event": "stream_started", "meeting_id": "..." }
{ "event": "transcript_chunk", "payload": {"text": "Ahmed said", "final": false} }
{ "event": "transcript_chunk", "payload": {"text": "Ahmed said deploy.", "final": true} }
{ "event": "translation_chunk", "payload": {"en": "...", "ar": "...", "original": "..."} }
{ "event": "stream_ended", "transcript_length": 1234 }
{ "event": "pong" }
```

---

## WebSocket: Employee Dashboard

```
WS ws://localhost:8000/ws/dashboard?employee_id=UUID&meeting_id=UUID
```

### Server → Client (JSON events)
```json
{ "event": "connected", "employee_id": "...", "meeting_id": "..." }

// Personal task — sent ONLY to assigned employee
{ "event": "task_extracted", "payload": {
    "id": "task-uuid",
    "title": "Deploy backend service",
    "priority": "HIGH",
    "deadline": "2025-01-17",
    "meeting_id": "...",
    "meeting_title": "Q2 Sprint Planning"
  }
}

// Summary — sent to ALL attendees
{ "event": "summary_ready", "payload": {
    "overview": "...",
    "key_points": [...],
    "decisions": [...],
    "full_text_ar": "..."
  }
}

{ "event": "meeting_ended", "payload": { "meeting_id": "...", "tasks_count": 5 } }
```

---

## Complete End-to-End Flow

```
1. POST /auth/register  × N employees
2. POST /auth/login     → get JWT token
3. POST /meeting/start  → get meeting_id
4. WS /ws/meeting/stream?meeting_id=...&employee_id=...
   ├── stream PCM audio bytes
   ├── receive: transcript_chunk (partial + final)
   ├── receive: translation_chunk (en + ar)
   └── send: {"action": "end_stream"}
5. POST /meeting/end { meeting_id }
   └── async pipeline starts:
       ├── aggregate transcript from Redis
       ├── translate to Arabic
       ├── persist Transcript
       ├── extract tasks (Groq LLM)
       ├── resolve assignees (NER + LLM)
       ├── push tasks to assigned employee dashboards (WS)
       ├── generate summary (Groq LLM)
       ├── push summary to ALL attendees (WS)
       └── mark meeting COMPLETED
6. GET /meeting/{id}/summary        → all attendees
7. GET /employee/{id}/tasks         → per employee
8. GET /meeting/{id}/transcript     → bilingual transcript
```

---

## Task Delivery Logic

Given attendees: Ahmed, Marwa, Sara
After meeting ends:

| Dashboard | Receives |
|-----------|----------|
| Ahmed | Only tasks assigned to Ahmed |
| Marwa | Only tasks assigned to Marwa |
| Sara | Only tasks assigned to Sara (empty if none) |
| All | Meeting summary (key points, decisions, next steps) |
| All | Full bilingual transcript (English + Arabic) |
