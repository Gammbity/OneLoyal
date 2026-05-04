from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.sales.schemas import normalize_currency

T = TypeVar("T")


class ERPCustomerDTO(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    email: EmailStr | None = None
    tax_id: str | None = Field(default=None, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    last_seen_at: datetime | None = None


class ERPSaleDTO(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    source_key: str | None = Field(default=None, min_length=1, max_length=512)
    customer_external_id: str = Field(min_length=1, max_length=255)
    document_kind: str = Field(min_length=1, max_length=32)
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
    payment_status: str = Field(default="unknown", max_length=32)
    document_status: str = Field(default="unknown", max_length=32)
    erp_document_type: str | None = Field(default=None, max_length=120)
    external_document_number: str | None = Field(default=None, max_length=255)
    external_updated_at: datetime | None = None
    is_deleted_in_source: bool = False
    is_archived_in_source: bool = False
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    content_hash: str | None = Field(default=None, max_length=128)

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


@dataclass(frozen=True)
class ProviderConnectionResult:
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderRowError:
    external_id: str | None
    error_code: str
    message: str
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderFetchResult[T]:
    items: list[T]
    next_cursor: dict[str, Any] | None = None
    has_more: bool = False
    stats: dict[str, Any] = field(default_factory=dict)
    errors: list[ProviderRowError] = field(default_factory=list)


class ERPProvider(Protocol):
    supports_customers: bool
    supports_sales: bool

    async def test_connection(self) -> ProviderConnectionResult:
        raise NotImplementedError

    async def fetch_customers(
        self,
        cursor: Mapping[str, Any] | None = None,
    ) -> ProviderFetchResult[ERPCustomerDTO]:
        raise NotImplementedError

    async def fetch_sales(
        self,
        cursor: Mapping[str, Any] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ProviderFetchResult[ERPSaleDTO]:
        raise NotImplementedError
