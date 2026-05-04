from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DomainEventResponse(BaseModel):
    id: UUID
    company_id: UUID | None
    event_type: str
    aggregate_type: str
    aggregate_id: UUID | None
    customer_id: UUID | None
    campaign_id: UUID | None
    gift_tier_id: UUID | None
    actor_user_id: UUID | None
    actor_customer_id: UUID | None
    correlation_id: str | None
    request_id: str | None
    payload_json: dict[str, Any]
    status: str
    attempts: int
    last_error: str | None
    occurred_at: datetime
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
