from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlanResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    limits_json: dict[str, Any]
    features_json: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionResponse(BaseModel):
    id: UUID
    company_id: UUID
    plan_id: UUID
    status: str
    trial_starts_at: datetime | None
    trial_ends_at: datetime | None
    current_period_starts_at: datetime | None
    current_period_ends_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

