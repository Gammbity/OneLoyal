from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.modules.companies.schemas import CompanyResponse
from app.modules.customers.schemas import CustomerResponse


class MagicLinkCreateResponse(BaseModel):
    token_id: UUID
    raw_token: str
    expires_at: datetime
    portal_url: str | None = None


class MagicLinkListItem(BaseModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    expires_at: datetime
    used_at: datetime | None
    last_used_at: datetime | None
    use_count: int
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PortalSessionRequest(BaseModel):
    token: str = Field(min_length=16)


class PortalSessionResponse(BaseModel):
    portal_access_token: str
    token_type: str = "bearer"
    expires_in: int
    customer: CustomerResponse
    company: CompanyResponse


class PortalMeResponse(BaseModel):
    customer: CustomerResponse
    company: CompanyResponse


class PortalCampaignResponse(BaseModel):
    id: UUID
    company_id: UUID
    title: str
    description: str | None
    start_date: date
    end_date: date
    status: str
    currency: str
    allow_claims: bool

    model_config = ConfigDict(from_attributes=True)


class PortalGiftTierResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    title: str
    description: str | None
    required_amount_minor: int
    currency: str
    image_url: str | None
    stock_tracking_mode: str
    stock_quantity: int | None
    sort_order: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PortalProgressSnapshotResponse(BaseModel):
    is_snapshot_available: bool
    total_amount_minor: int
    currency: str
    current_tier_id: UUID | None
    current_tier_title: str | None
    next_tier_id: UUID | None
    next_tier_title: str | None
    amount_left_minor: int
    progress_percent: Decimal
    progress_percent_basis_points: int
    calculated_at: datetime | None = None

    @field_serializer("progress_percent")
    def serialize_progress_percent(self, value: Decimal) -> str:
        return f"{value:.2f}"


class PortalProgressResponse(BaseModel):
    campaign: PortalCampaignResponse
    customer: CustomerResponse
    progress: PortalProgressSnapshotResponse
    gift_tiers: list[PortalGiftTierResponse]


class PortalPurchaseHistoryItem(BaseModel):
    document_date: date
    effective_date: date
    document_kind: str
    external_document_number: str | None
    gross_amount_minor: int
    amount_sign: int
    currency: str
    payment_status: str
    document_status: str

    model_config = ConfigDict(from_attributes=True)

