# OneLoyal Deployment Guide

This guide covers how to deploy OneLoyal using Docker and Compose.

## Prerequisites

- Docker and Docker Compose
- A domain name (for production)
- SMTP/SMS provider credentials (future steps)
- MoySklad account (optional for ERP sync)

## Local Development

1. **Setup Environment**
   ```bash
   cd backend
   cp .env.example .env
   # Fill in local secrets if needed
   ```

2. **Start Services**
   ```bash
   docker compose up --build
   ```
   - API: http://localhost:8000
   - Admin/Portal: http://localhost:5173
   - Postgres: localhost:5432
   - Redis: localhost:6379

## Production Deployment

### 1. Preparation

Copy the production environment example and fill in secure values:
```bash
cp .env.prod.example .env.prod
```

**Required secret generation:**

- **SECRET_KEY**: Generate a long random string.
  ```bash
  openssl rand -hex 32
  ```

- **ENCRYPTION_KEY**: Generate a Fernet key for credential encryption.
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

- **Database Password**: Use a strong password for `POSTGRES_PASSWORD` and `DATABASE_URL`.

### 2. Startup

Run the production compose file:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This will:
1. Start Postgres and Redis.
2. Run database migrations (`migrate` service).
3. Start the API, Worker, and Beat services.
4. Build and start the Frontend (Nginx).

### 3. Verification

- **Check API health**: `curl http://your-domain/api/v1/health`
- **Check DB connectivity**: `curl http://your-domain/api/v1/health/db`
- **Check Logs**:
  ```bash
  docker compose -f docker-compose.prod.yml logs -f api
  docker compose -f docker-compose.prod.yml logs -f worker
  ```

### 4. Post-Deployment

**Create first company and owner:**
Use the registration endpoint:
```bash
curl -X POST http://your-domain/api/v1/auth/register-company \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "My Company",
    "company_slug": "my-company",
    "owner_full_name": "Admin User",
    "owner_email": "admin@example.com",
    "owner_password": "secure-password"
  }'
```

## Maintenance

### Database Migrations
To run migrations manually:
```bash
docker compose -f docker-compose.prod.yml run --rm migrate
```

### Backups
Recommended backup strategy for PostgreSQL:
```bash
docker exec oneloyal-postgres-1 pg_dump -U oneloyal oneloyal > backup_$(date +%F).sql
```

### Security Notes
- Containers run as a non-root user (`oneloyal`).
- `DEBUG` is set to `false`.
- CORS is restricted to your production domains.
- Sensitive fields are redacted in logs.
- Credentials in the database are encrypted at rest.
- **Note**: This setup does not include SSL/TLS. You should use a reverse proxy (like Cloudflare, Traefik, or a host-level Nginx) to handle HTTPS.

## Troubleshooting

- **Redis connection issues**: Ensure the `REDIS_URL` uses the service name `redis`.
- **Migration failure**: Check logs of the `migrate` service. Ensure the DB is reachable.
- **CORS issues**: Verify `CORS_ORIGINS` in `.env.prod` matches your frontend URL.
- **Worker not processing**: Check if `CELERY_BROKER_URL` matches the Redis configuration.
