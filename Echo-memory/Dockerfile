# SyncVerse Echo - production image, designed to run on Hugging Face Spaces
# (Docker SDK) or any container platform.
FROM python:3.11-slim

# Hugging Face Spaces run containers as a non-root user by default; create
# one explicitly so file permissions behave the same everywhere.
RUN useradd --create-home --uid 1000 echo

WORKDIR /app

# System deps needed by psycopg2 and chromadb's onnxruntime dependency.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Hugging Face Spaces persistent storage is mounted at /data - this is
# where ChromaDB will keep its vector index across restarts.
RUN mkdir -p /data/chroma && chown -R echo:echo /data /app

ENV CHROMA_PERSIST_DIR=/data/chroma \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ANONYMIZED_TELEMETRY=False

USER echo

# Hugging Face Spaces expects the app to listen on port 7860.
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:7860/echo/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
