from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    base_currency: str
    timezone: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanySettingsResponse(BaseModel):
    id: UUID
    company_id: UUID
    fiscal_year_start_month: int
    fiscal_year_start_day: int
    default_campaign_duration_days: int | None
    default_campaign_rules_json: dict[str, Any]
    customer_portal_branding_json: dict[str, Any]
    sync_frequency_minutes: int | None
    notification_preferences_json: dict[str, Any]
    reward_claim_enabled_default: bool
    data_retention_days: int | None
    extra_settings_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdateCompanySettingsRequest(BaseModel):
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    fiscal_year_start_day: int | None = Field(default=None, ge=1, le=31)
    default_campaign_duration_days: int | None = Field(default=None, ge=1)
    default_campaign_rules_json: dict[str, Any] | None = None
    customer_portal_branding_json: dict[str, Any] | None = None
    sync_frequency_minutes: int | None = Field(default=None, ge=5)
    notification_preferences_json: dict[str, Any] | None = None
    reward_claim_enabled_default: bool | None = None
    data_retention_days: int | None = Field(default=None, ge=1)
    extra_settings_json: dict[str, Any] | None = None

