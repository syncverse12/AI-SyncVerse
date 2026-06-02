# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for compiling packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Download spaCy model into the install prefix
RUN /install/bin/python -m spacy download en_core_web_sm


# ── Stage 2: production image ─────────────────────────────────────────────────
FROM python:3.11-slim AS production

# Non-root user (Hugging Face Spaces requirement)
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /home/appuser/app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=appuser:appuser . .

USER appuser

# Hugging Face Spaces expects port 7860
EXPOSE 7860

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
