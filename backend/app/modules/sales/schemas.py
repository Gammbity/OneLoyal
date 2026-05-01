from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.customers.models import ExternalProvider
from app.modules.sales.models import (
    PaymentStatus,
    SaleDocumentKind,
    SaleDocumentStatus,
    SaleSourceType,
)


def normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("currency must be a 3-letter ISO currency code")
    return normalized


class SaleRecordCreateRequest(BaseModel):
    customer_id: UUID
    source_type: SaleSourceType
    source_key: str = Field(min_length=1, max_length=512)
    provider: ExternalProvider
    document_kind: SaleDocumentKind
    erp_document_type: str | None = Field(default=None, max_length=120)
    external_document_id: str | None = Field(default=None, max_length=255)
    external_document_number: str | None = Field(default=None, max_length=255)
    external_updated_at: datetime | None = None
    document_date: date
    effective_date: date
    gross_amount_minor: int = Field(ge=0)
    net_amount_minor: int | None = Field(default=None, ge=0)
    vat_amount_minor: int | None = Field(default=None, ge=0)
    discount_amount_minor: int | None = Field(default=None, ge=0)
    paid_amount_minor: int | None = Field(default=None, ge=0)
    debt_amount_minor: int | None = Field(default=None, ge=0)
    amount_sign: int = Field(default=1)
    currency: str = Field(min_length=3, max_length=3)
    currency_scale: int = Field(default=0, ge=0)
    payment_status: PaymentStatus = PaymentStatus.UNKNOWN
    document_status: SaleDocumentStatus = SaleDocumentStatus.UNKNOWN
    source_customer_external_id: str | None = Field(default=None, max_length=255)
    raw_payload_json: dict[str, Any] | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("amount_sign")
    @classmethod
    def validate_amount_sign(cls, value: int) -> int:
        if value not in {1, -1}:
            raise ValueError("amount_sign must be 1 or -1")
        return value


class SaleRecordResponse(BaseModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    integration_id: UUID | None
    import_batch_id: UUID | None
    source_type: str
    source_key: str
    provider: str
    erp_document_type: str | None
    document_kind: str
    external_document_id: str | None
    external_document_number: str | None
    external_updated_at: datetime | None
    document_date: date
    effective_date: date
    gross_amount_minor: int
    net_amount_minor: int | None
    vat_amount_minor: int | None
    discount_amount_minor: int | None
    paid_amount_minor: int | None
    debt_amount_minor: int | None
    amount_sign: int
    currency: str
    currency_scale: int
    payment_status: str
    document_status: str
    is_deleted_in_source: bool
    is_archived_in_source: bool
    source_customer_external_id: str | None
    content_hash: str | None
    synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

