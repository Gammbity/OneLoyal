import asyncio
from typing import Any

from app.db.session import AsyncSessionLocal
from app.modules.notifications.service import notification_service
from app.workers.celery_app import celery_app


@celery_app.task(name="app.notifications.process_domain_events")
def process_domain_events_task() -> dict[str, Any]:
    return asyncio.run(_process_domain_events())


async def _process_domain_events() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        stats = await notification_service.process_pending_domain_events(session)
        await session.commit()
        return stats.model_dump()


@celery_app.task(name="app.notifications.process_notification_events")
def process_notification_events_task() -> dict[str, Any]:
    return asyncio.run(_process_notification_events())


async def _process_notification_events() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        stats = await notification_service.send_pending_notifications(session)
        await session.commit()
        return stats.model_dump()
