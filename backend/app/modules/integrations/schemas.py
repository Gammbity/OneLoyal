from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.integrations.models import IntegrationProvider, IntegrationStatus


class IntegrationCreateRequest(BaseModel):
    provider: IntegrationProvider
    name: str = Field(min_length=1, max_length=255)
    settings_json: dict[str, Any] | None = None
    credentials_json: dict[str, Any] | None = None


class IntegrationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: IntegrationStatus | None = None
    settings_json: dict[str, Any] | None = None
    credentials_json: dict[str, Any] | None = None


class IntegrationResponse(BaseModel):
    id: UUID
    company_id: UUID
    provider: str
    name: str
    status: str
    settings_json: dict[str, Any]
    last_attempted_sync_at: datetime | None
    last_successful_sync_at: datetime | None
    last_scheduled_sync_at: datetime | None
    next_sync_at: datetime | None
    sync_cursor_json: dict[str, Any]
    has_active_credentials: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntegrationTestResponse(BaseModel):
    ok: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
