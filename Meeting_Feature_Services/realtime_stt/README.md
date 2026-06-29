---
title: Real-Time Speech-to-Text
emoji: 🎙️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# Real-Time Speech-to-Text Service

Standalone real-time transcription microservice extracted from the
[Sentry AI Burnout Detection Engine](https://github.com/AhmedMostafaDev12/Sentry_AI_burnout_detection_engine).

Powered by **AssemblyAI**. Supports both file upload and live WebSocket streaming.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service status + API key check |
| `POST` | `/transcribe/file` | Upload an audio file → full transcript JSON |
| `WebSocket` | `/transcribe/stream` | Stream raw PCM → partial + final events |
| `GET` | `/docs` | Interactive Swagger UI |
| `GET` | `/redoc` | ReDoc API reference |

---

## Audio format requirements

### File upload (`POST /transcribe/file`)
AssemblyAI accepts files directly — no conversion needed on your side.

| Property | Value |
|----------|-------|
| Formats | MP3, WAV, M4A, FLAC, OGG, WEBM, MP4 (audio), … |
| Sample rate | Any (AssemblyAI resamples internally) |
| Channels | Mono or stereo |

### WebSocket streaming (`WS /transcribe/stream`)

| Property | Required value |
|----------|---------------|
| Encoding | PCM signed 16-bit little-endian (**LINEAR16**) |
| Sample rate | **16 000 Hz** |
| Channels | **Mono** |
| Chunk size | 3 200 bytes recommended (= 100 ms at 16 kHz) |

---

## Real-time processing workflow

```
Microphone / audio source
        │  PCM LINEAR16 chunks (~100 ms each)
        ▼
WebSocket client ──binary frames──► FastAPI /transcribe/stream
                                            │
                                    RealtimeTranscriber
                                    (AssemblyAI RT SDK)
                                            │
                        ◄── JSON events (partial / final) ──
```

WebSocket event format:
```json
{"type": "partial", "text": "hello wor"}
{"type": "final",   "text": "Hello world."}
{"type": "error",   "text": "<description>"}
{"type": "closed",  "text": ""}
```

---

## Model & libraries

| Component | Library / Service | Version |
|-----------|------------------|---------|
| Speech-to-text (file) | AssemblyAI Batch API (Universal-2 model) | `assemblyai==0.35.0` |
| Speech-to-text (stream) | AssemblyAI Real-Time API | `assemblyai==0.35.0` |
| Web framework | FastAPI | `0.117.1` |
| ASGI server | Uvicorn | `0.36.0` |
| WebSocket transport | `websockets` | `16.0` |

---

## Deploying to Hugging Face Spaces

### Step 1 — Fork or push this repository

```bash
git clone https://github.com/<your-org>/realtime-stt
cd realtime-stt

# Create a new HF Space (Docker SDK)
huggingface-cli repo create realtime-stt --type space --space-sdk docker
git remote add hf https://huggingface.co/spaces/<your-username>/realtime-stt
git push hf main
```

### Step 2 — Add your API key as a Space Secret

1. Open your Space → **Settings** → **Repository secrets**
2. Add a new secret:
   - **Name**: `ASSEMBLYAI_API_KEY`
   - **Value**: your key from [assemblyai.com/dashboard](https://www.assemblyai.com/dashboard)

Hugging Face injects Space Secrets as environment variables at container
startup. The app reads `ASSEMBLYAI_API_KEY` via `os.getenv()`.

### Step 3 — The Space builds and starts automatically

HF builds the Docker image from the `Dockerfile` in the repo root and
starts the container. The app will be live at:

```
https://<your-username>-realtime-stt.hf.space/docs
```

> **Port**: HF sets `PORT=7860` automatically. The `CMD` in the Dockerfile
> reads `$PORT` at runtime, so no manual changes are needed.

---

## Running locally

### Option A — Docker (identical to HF deployment)

```bash
docker build -t realtime-stt .
docker run -p 7860:7860 -e ASSEMBLYAI_API_KEY=your_key realtime-stt
```

Service is available at http://localhost:7860/docs

### Option B — Python directly

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env → set ASSEMBLYAI_API_KEY=your_key

uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

---

## Quick API tests

```bash
# Health check
curl http://localhost:7860/health

# File transcription
curl -X POST http://localhost:7860/transcribe/file \
  -F "file=@meeting.mp3" \
  -F "language_detection=true"
```

WebSocket stream (Python):
```python
import asyncio, websockets, json

async def test():
    uri = "ws://localhost:7860/transcribe/stream"
    async with websockets.connect(uri) as ws:
        # Send 1 second of silence (16kHz mono LINEAR16)
        await ws.send(b"\x00" * 32000)
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        print(json.loads(msg))

asyncio.run(test())
```

---

## Project structure

```
realtime_stt/
├── Dockerfile                 ← HF Docker Space build definition
├── README.md                  ← this file (Space card + docs)
├── requirements.txt           ← pinned production dependencies
├── .env.example               ← local dev template
├── app/
│   ├── __init__.py
│   ├── main.py                ← FastAPI app (REST + WebSocket)
│   └── transcriber.py         ← AssemblyAI engine (file + streaming)
├── mic_client.py              ← CLI microphone demo
└── tests/
    └── test_transcriber.py
```

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ASSEMBLYAI_API_KEY` | **Yes** | AssemblyAI API key — set as a Space Secret on HF |
| `PORT` | No | Listening port (HF sets this to `7860` automatically) |

Never commit your API key to the repository.
Use **Space Secrets** on HF or a local `.env` file (git-ignored).
