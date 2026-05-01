from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.campaigns.models import StockTrackingMode


def normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("currency must be a 3-letter ISO currency code")
    return normalized


class CampaignCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_date: date
    end_date: date
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    rules_json: dict[str, Any] | None = None
    visibility_settings_json: dict[str, Any] | None = None
    allow_claims: bool | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_currency(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "CampaignCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class CampaignUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    rules_json: dict[str, Any] | None = None
    visibility_settings_json: dict[str, Any] | None = None
    allow_claims: bool | None = None


class CampaignResponse(BaseModel):
    id: UUID
    company_id: UUID
    title: str
    description: str | None
    start_date: date
    end_date: date
    status: str
    currency: str
    rules_json: dict[str, Any]
    visibility_settings_json: dict[str, Any]
    allow_claims: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GiftTierCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    required_amount_minor: int = Field(gt=0)
    image_url: str | None = Field(default=None, max_length=2048)
    stock_tracking_mode: StockTrackingMode = StockTrackingMode.NONE
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool = True


class GiftTierUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    required_amount_minor: int | None = Field(default=None, gt=0)
    image_url: str | None = Field(default=None, max_length=2048)
    stock_tracking_mode: StockTrackingMode | None = None
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class GiftTierResponse(BaseModel):
    id: UUID
    company_id: UUID
    campaign_id: UUID
    title: str
    description: str | None
    required_amount_minor: int
    currency: str
    image_url: str | None
    stock_tracking_mode: str
    stock_quantity: int | None
    reserved_quantity: int
    fulfilled_quantity: int
    available_quantity: int | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GiftTierReorderRequest(BaseModel):
    tier_ids: list[UUID] = Field(min_length=1)

