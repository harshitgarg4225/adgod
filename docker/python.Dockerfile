# One image for all Python services (bff-api, webhook-intake, closer-worker,
# agent-worker, cron-dispatch). The Railway service overrides the start command.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: libpq for psycopg, build essentials kept minimal.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install ".[llm,storage]"

# App code (migrations, etc.)
COPY alembic.ini ./
COPY alembic ./alembic

# Non-root runtime user.
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default command (overridden per Railway service). PORT is provided by Railway.
CMD ["sh", "-c", "gunicorn leadpilot.bff.app:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000}"]
