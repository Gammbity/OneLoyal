from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SyncRunResponse(BaseModel):
    id: UUID
    company_id: UUID
    integration_id: UUID
    sync_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    cursor_before_json: dict[str, Any]
    cursor_after_json: dict[str, Any]
    stats_json: dict[str, Any]
    error_summary: str | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SyncErrorResponse(BaseModel):
    id: UUID
    company_id: UUID
    sync_run_id: UUID
    entity_type: str
    external_id: str | None
    severity: str
    error_code: str
    message: str
    raw_payload_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
