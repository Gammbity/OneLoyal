from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.customers.models import CustomerStatus, ExternalProvider


class CustomerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    email: EmailStr | None = None
    tax_id: str | None = Field(default=None, max_length=120)
    metadata_json: dict[str, Any] | None = None


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    email: EmailStr | None = None
    tax_id: str | None = Field(default=None, max_length=120)
    status: CustomerStatus | None = None
    metadata_json: dict[str, Any] | None = None


class CustomerResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    phone: str | None
    email: str | None
    tax_id: str | None
    status: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerExternalRefCreateRequest(BaseModel):
    customer_id: UUID
    provider: ExternalProvider
    external_id: str = Field(min_length=1, max_length=255)
    external_name: str | None = Field(default=None, max_length=255)
    external_phone: str | None = Field(default=None, max_length=64)
    external_email: EmailStr | None = None
    raw_payload_json: dict[str, Any] | None = None


class CustomerExternalRefResponse(BaseModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    provider: str
    external_id: str
    external_name: str | None
    external_phone: str | None
    external_email: str | None
    raw_payload_json: dict[str, Any]
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignCustomerRequest(BaseModel):
    sales_manager_user_id: UUID


class CustomerAssignmentResponse(BaseModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    sales_manager_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

