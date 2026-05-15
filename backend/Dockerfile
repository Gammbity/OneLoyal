# Build stage
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Runtime stage
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Create non-root user
RUN groupadd -g 1000 oneloyal && \
    useradd -u 1000 -g oneloyal -s /bin/sh oneloyal && \
    chown -R oneloyal:oneloyal /app

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder --chown=oneloyal:oneloyal /app/.venv /app/.venv
COPY --chown=oneloyal:oneloyal alembic ./alembic
COPY --chown=oneloyal:oneloyal alembic.ini ./alembic.ini
COPY --chown=oneloyal:oneloyal app ./app

USER oneloyal

EXPOSE 8000

# Default command for API. Can be overridden in compose for worker/beat.
# Using uvicorn directly for simplicity, gunicorn with uvicorn workers is also common for prod.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
