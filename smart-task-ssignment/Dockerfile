FROM python:3.12-slim

WORKDIR /app

# System deps needed only for the healthcheck (curl). Kept minimal.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user — matches the security posture used across the other
# SyncVerse microservices (risk_forecast, attrition-intelligence, etc.).
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Railway assigns PORT dynamically; 8000 is only the local/documentation
# default (used by docker-compose and `docker run` without -e PORT=...).
ENV PORT=8000
EXPOSE 8000

# Shell form is required here so ${PORT} is expanded at container start —
# the previous exec-form array baked in a literal "7860" that ignored
# whatever PORT Railway actually injected, so the platform's health probe
# could never reach the app.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f "http://localhost:${PORT}/health" || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1
