from typing import Any
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.modules.sync.service import sync_service
from app.workers.async_runtime import run_celery_async
from app.workers.celery_app import celery_app


@celery_app.task(name="app.sync.execute")
def sync_integration_task(sync_run_id: str) -> dict[str, Any]:
    return run_celery_async(_execute_sync_integration_task(UUID(sync_run_id)))


async def _execute_sync_integration_task(sync_run_id: UUID) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        sync_run = await sync_service.execute_sync_run(
            session,
            sync_run_id=sync_run_id,
            use_redis_lock=True,
        )
        await session.commit()
        return {
            "sync_run_id": str(sync_run.id),
            "status": sync_run.status,
        }


@celery_app.task(name="app.sync.schedule_due")
def schedule_due_integrations_task() -> dict[str, Any]:
    return run_celery_async(_schedule_due_integrations_task())


async def _schedule_due_integrations_task() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        stats = await sync_service.create_due_scheduled_sync_runs(session)
        await session.commit()

    for item in stats.get("queued_sync_runs", []):
        sync_service.publish_sync_run(
            UUID(item["sync_run_id"]),
            task_id=item.get("task_id"),
        )
    return stats
