# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Core deps first for layer caching
COPY requirements.txt requirements-ml.txt ./
RUN pip install -r requirements.txt

# Local BGE embeddings (~1 GB CPU torch). Build with --build-arg INSTALL_ML=false
# when using EMBEDDING_PROVIDER=openai to keep the image small.
ARG INSTALL_ML=true
RUN if [ "$INSTALL_ML" = "true" ]; then pip install -r requirements-ml.txt; fi

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY samples ./samples

RUN useradd --create-home --uid 10001 screeniq \
    && mkdir -p /app/.cache/huggingface \
    && chown -R screeniq:screeniq /app
USER screeniq

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

# Migrate, then serve. Background pipelines run in-process, so scale with more
# containers rather than more workers per container.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
