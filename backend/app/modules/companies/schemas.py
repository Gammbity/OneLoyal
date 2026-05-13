from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.users.schemas import UserResponse


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


class CreateCompanyRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    company_slug: str | None = Field(default=None, min_length=2, max_length=120)
    owner_full_name: str | None = Field(default=None, min_length=1, max_length=255)
    owner_email: EmailStr
    owner_password: str = Field(min_length=8)

    @field_validator("company_slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized.replace("-", "").isalnum():
            raise ValueError(
                "slug may contain only lowercase letters, numbers, and hyphens"
            )
        return normalized


class CompanyProvisionResponse(BaseModel):
    company: CompanyResponse
    owner: UserResponse
    login_path: str


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
