from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RewardClaimCreateRequest(BaseModel):
    campaign_id: UUID
    customer_id: UUID
    gift_tier_id: UUID
    customer_comment: str | None = Field(default=None, max_length=5000)


class PortalRewardClaimCreateRequest(BaseModel):
    gift_tier_id: UUID
    customer_comment: str | None = Field(default=None, max_length=5000)


class RewardClaimActionRequest(BaseModel):
    admin_comment: str | None = Field(default=None, max_length=5000)


class RewardClaimResponse(BaseModel):
    id: UUID
    company_id: UUID
    campaign_id: UUID
    customer_id: UUID
    gift_tier_id: UUID
    status: str
    customer_comment: str | None
    admin_comment: str | None
    decided_by_user_id: UUID | None
    decided_at: datetime | None
    fulfilled_by_user_id: UUID | None
    fulfilled_at: datetime | None
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    customer_name: str | None = None
    campaign_title: str | None = None
    gift_tier_title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
