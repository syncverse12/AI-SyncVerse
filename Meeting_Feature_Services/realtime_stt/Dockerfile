# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Real-Time Speech-to-Text Service
# Target: Hugging Face Docker Space
#
# HF Space requirements satisfied:
#   • Listens on 0.0.0.0:$PORT  (defaults to 7860 if PORT not set)
#   • Runs as non-root user (uid 1000) — HF best practice
#   • Single ENV var needed at runtime: ASSEMBLYAI_API_KEY
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# ── Labels (displayed in the HF Space UI) ────────────────────────────────────
LABEL maintainer="Sentry AI Team"
LABEL description="Real-Time Speech-to-Text microservice using AssemblyAI"

# ── System dependencies ───────────────────────────────────────────────────────
# curl  → healthcheck
# No audio libs needed: AssemblyAI is cloud-based (no local model)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user (uid 1000 matches HF Space sandbox uid) ────────────────────
RUN useradd --uid 1000 --create-home appuser

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
# Copy requirements first so Docker layer cache is reused on code-only changes
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY app/ ./app/

# ── Ownership ─────────────────────────────────────────────────────────────────
RUN chown -R appuser:appuser /app
USER appuser

# ── Runtime configuration ─────────────────────────────────────────────────────
# PORT is injected by Hugging Face (default 7860).
# ASSEMBLYAI_API_KEY must be set as a Space Secret in the HF settings UI.
ENV PORT=7860 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# ── Expose ────────────────────────────────────────────────────────────────────
EXPOSE ${PORT}

# ── Entrypoint ────────────────────────────────────────────────────────────────
# Shell form so $PORT is expanded at runtime.
# --workers 1 is intentional: AssemblyAI real-time sessions are stateful;
# multiple workers would require a shared session store.
CMD uvicorn app.main:app \
        --host 0.0.0.0 \
        --port ${PORT} \
        --workers 1 \
        --log-level info
