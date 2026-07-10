# ─────────────────────────────────────────────────────────────────────────────
# AI Dynamic Project Planner — Dockerfile
# Structured app/ layout.
# Compatible with Hugging Face Spaces (port 7860, root user).
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

LABEL description="AI Dynamic Project Planner — FastAPI service"
LABEL version="1.0.0"

# System deps (curl for HEALTHCHECK only)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Python env
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /code

# Install deps (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source — preserve the app/ and planner/ package structure
COPY app/     ./app/
COPY planner/ ./planner/

# Hugging Face Spaces requires exactly port 7860.
# Railway (and most other PaaS) inject a dynamic $PORT at runtime instead,
# so default to 7860 for HF Spaces / local Docker, but honor $PORT when set.
ENV PORT=7860
EXPOSE 7860

# Health check — uses the same $PORT the app actually binds to
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# workers=1 keeps the in-memory store consistent across requests
# Add Redis + increase workers for horizontal scaling
# Shell form (not exec-array form) so ${PORT} is expanded at container start
CMD uvicorn app.main:app \
     --host 0.0.0.0 \
     --port ${PORT} \
     --workers 1 \
     --log-level info
