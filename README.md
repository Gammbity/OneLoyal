# OneLoyal

B2B ERP-based loyalty platform for managing customer gift programs.

## Project Structure

- **[backend/](./backend)**: FastAPI, SQLAlchemy, Celery, PostgreSQL.
- **[frontend/](./frontend)**: React, Vite, TypeScript.
- **[docs/deployment.md](./docs/deployment.md)**: Deployment Guide.

## Quick Start (Docker)

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

For more details, see the [Deployment Guide](./docs/deployment.md).
