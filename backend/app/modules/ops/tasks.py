import asyncio
from typing import Any

from app.db.session import AsyncSessionLocal
from app.modules.ops.service import (
    notification_recovery_service,
    sync_recovery_service,
)
from app.workers.celery_app import celery_app


@celery_app.task(name="app.ops.recover_stuck_syncs")
def recover_stuck_syncs_task() -> dict[str, Any]:
    return asyncio.run(_recover_stuck_syncs())


async def _recover_stuck_syncs() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        stats = await sync_recovery_service.recover_stuck_sync_runs(session)
        await session.commit()
        return stats.model_dump()


@celery_app.task(name="app.ops.recover_notifications")
def recover_notifications_task() -> dict[str, Any]:
    return asyncio.run(_recover_notifications())


async def _recover_notifications() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        stats = await notification_recovery_service.recover_notifications(session)
        await session.commit()
        return stats.model_dump()
