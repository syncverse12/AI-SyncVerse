FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV APP_MODE=demo \
    PYTHONUNBUFFERED=1

EXPOSE 7860

# Shell form so ${PORT:-7860} expands — Railway injects $PORT at runtime.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}
