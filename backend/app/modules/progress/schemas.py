from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer


class CustomerCampaignProgressResponse(BaseModel):
    id: UUID
    company_id: UUID
    campaign_id: UUID
    customer_id: UUID
    customer_name: str | None
    total_amount_minor: int
    currency: str
    current_tier_id: UUID | None
    current_tier_title: str | None
    next_tier_id: UUID | None
    next_tier_title: str | None
    amount_left_minor: int
    progress_percent: Decimal
    progress_percent_basis_points: int
    calculation_version: int
    stats_json: dict[str, Any]
    calculated_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("progress_percent")
    def serialize_progress_percent(self, value: Decimal) -> str:
        return f"{value:.2f}"


class RecalculateCampaignResponse(BaseModel):
    campaign_id: UUID
    recalculated_count: int
    skipped_count: int
    failed_count: int
    affected_customer_count: int

