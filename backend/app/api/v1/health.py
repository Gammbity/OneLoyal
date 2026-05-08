from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.core.settings import Settings, get_settings
from app.db.session import get_db

router = APIRouter(tags=["health"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    checks: dict[str, Any] | None = None


class DBHealthResponse(BaseModel):
    status: str
    database: str


class RedisHealthResponse(BaseModel):
    status: str
    redis: str


class CeleryHealthResponse(BaseModel):
    status: str
    broker: str


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/health/db", response_model=DBHealthResponse)
async def db_health_check(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DBHealthResponse:
    try:
        await session.execute(text("SELECT 1"))
        return DBHealthResponse(status="ok", database="connected")
    except Exception as exc:
        return DBHealthResponse(status="error", database=str(exc))


@router.get("/health/redis", response_model=RedisHealthResponse)
async def redis_health_check() -> RedisHealthResponse:
    try:
        client = get_redis_client()
        await client.ping()
        return RedisHealthResponse(status="ok", redis="connected")
    except Exception as exc:
        return RedisHealthResponse(status="error", redis=str(exc))


@router.get("/health/celery", response_model=CeleryHealthResponse)
async def celery_health_check() -> CeleryHealthResponse:
    # This checks broker connectivity which is often enough for "health"
    try:
        from app.workers.celery_app import celery_app

        with celery_app.connection_for_read() as conn:
            conn.ensure_connection(max_retries=1)
        return CeleryHealthResponse(status="ok", broker="connected")
    except Exception as exc:
        return CeleryHealthResponse(status="error", broker=str(exc))


@router.get("/health/full", response_model=HealthResponse)
async def full_health_check(
    settings: SettingsDep,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HealthResponse:
    checks = {}
    overall_status = "ok"

    # DB Check
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        overall_status = "error"

    # Redis Check
    try:
        client = get_redis_client()
        await client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
        overall_status = "error"

    # Celery Broker Check
    try:
        from app.workers.celery_app import celery_app

        with celery_app.connection_for_read() as conn:
            conn.ensure_connection(max_retries=1)
        checks["celery_broker"] = "ok"
    except Exception:
        checks["celery_broker"] = "error"
        overall_status = "error"

    return HealthResponse(
        status=overall_status,
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        checks=checks,
    )
