from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: UUID
    company_id: UUID | None
    actor_user_id: UUID | None
    actor_customer_id: UUID | None
    actor_type: str
    action: str
    entity_type: str
    entity_id: UUID | None
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    before_json: dict[str, Any]
    after_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
