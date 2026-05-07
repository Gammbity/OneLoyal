from celery import Celery

from app.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "oneloyal",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.modules.sync.tasks",
        "app.modules.notifications.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.sync_task_time_limit_seconds,
    task_soft_time_limit=settings.sync_task_soft_time_limit_seconds,
    beat_schedule={
        "schedule-due-integrations": {
            "task": "app.sync.schedule_due",
            "schedule": 60.0,
        },
        "process-domain-events-for-notifications": {
            "task": "app.notifications.process_domain_events",
            "schedule": 30.0,
        },
        "process-pending-notifications": {
            "task": "app.notifications.process_notification_events",
            "schedule": 30.0,
        },
    },
)


@celery_app.task(name="app.workers.debug")
def debug_task() -> dict[str, str]:
    return {"status": "ok"}
