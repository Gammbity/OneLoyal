from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class OpsStatusResponse(BaseModel):
    company_id: str
    sync_runs: dict[str, int]
    queued_sync_count: int
    running_sync_count: int
    stuck_queued_sync_count: int
    stuck_running_sync_count: int
    pending_notification_events_count: int
    failed_notification_events_count: int
    pending_domain_events_count: int
    failed_domain_events_count: int
    recent_failed_sync_errors_count: int
    active_integrations_count: int
    scheduled_integrations_count: int
    last_successful_sync_time: datetime | None
    last_failed_sync_time: datetime | None

    model_config = ConfigDict(from_attributes=True)


class RecoverStuckSyncsResponse(BaseModel):
    checked_count: int
    recovered_queued_count: int
    recovered_running_count: int


class RecoverNotificationsResponse(BaseModel):
    checked_count: int
    failed_count: int
    retried_count: int
