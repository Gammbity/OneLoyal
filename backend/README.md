# OneLoyal Backend

FastAPI backend foundation for the OneLoyal B2B ERP-based gift progress and loyalty SaaS platform.

This scaffold includes only the backend foundation:

- FastAPI app factory
- `/api/v1` router
- health endpoint
- pydantic-settings configuration
- reusable SQLAlchemy model mixins
- async SQLAlchemy engine/session
- Alembic async migration setup
- reusable pagination utilities
- Redis connection helper
- Celery app
- structured JSON logging
- request ID middleware
- standardized error responses
- password hashing, JWT, and encryption utility foundations
- Docker and Docker Compose
- pytest smoke tests

Business modules, auth, ERP integrations, reward calculation, and frontend code are intentionally not implemented yet.

## Project Structure

```text
backend/
  app/
    main.py
    api/v1/
    core/
    db/
    workers/
    common/
    integrations/
    modules/
  alembic/
  tests/
  pyproject.toml
  Dockerfile
  docker-compose.yml
```

## Local Setup With uv

```bash
cd backend
uv sync
cp .env.example .env
```

Generate local secrets before using authentication or encryption features:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use the first value for `SECRET_KEY` and the second value for `ENCRYPTION_KEY`.
`ENCRYPTION_KEY` must be a valid Fernet key.

If you run the API directly on your machine while PostgreSQL and Redis are exposed from Docker, change these values in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://oneloyal:oneloyal@localhost:5432/oneloyal
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

## Run Locally

Start PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
```

Run the API:

```bash
uv run uvicorn app.main:app --reload
```

Open:

```text
http://localhost:8000/api/v1/health
http://localhost:8000/docs
```

## Docker Compose

```bash
cd backend
cp .env.example .env
docker compose up --build
```

The API will be available at:

```text
http://localhost:8000
```

## Migrations

Create a migration:

```bash
uv run alembic revision --autogenerate -m "message"
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Inside Docker Compose:

```bash
docker compose run --rm api alembic upgrade head
```

## Tests

```bash
cd backend
uv run pytest
```

## Celery

Run the worker locally:

```bash
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
```

Run Celery through Docker Compose:

```bash
docker compose up worker
```
