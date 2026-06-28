FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ──────────────────────────────────────────────
# Runtime Image
# ──────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# Runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV APP_ENV=hf

COPY app/ ./app/
COPY scripts/ ./scripts/

# Optional directories
RUN mkdir -p /app/logs /app/ml_models /app/data

# Non-root user
RUN useradd -m syncverse && chown -R syncverse /app
USER syncverse

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]