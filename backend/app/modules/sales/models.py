from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company
from app.modules.customers.models import Customer, ExternalProvider


class SaleSourceType(StrEnum):
    ERP = "erp"
    CSV = "csv"
    MANUAL = "manual"


class SaleDocumentKind(StrEnum):
    SALE = "sale"
    RETURN = "return"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    CORRECTION = "correction"


class PaymentStatus(StrEnum):
    UNKNOWN = "unknown"
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"
    OVERPAID = "overpaid"


class SaleDocumentStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"
    CANCELLED = "cancelled"
    DELETED = "deleted"
    UNKNOWN = "unknown"


class SaleRecord(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "sale_records"
    __table_args__ = (
        UniqueConstraint("company_id", "source_key", name="uq_sale_records_source_key"),
        Index("ix_sale_records_company_id", "company_id"),
        Index("ix_sale_records_customer_id", "customer_id"),
        Index(
            "ix_sale_records_company_customer_effective_date",
            "company_id",
            "customer_id",
            "effective_date",
        ),
        Index(
            "ix_sale_records_company_effective_date",
            "company_id",
            "effective_date",
        ),
        Index(
            "ix_sale_records_company_currency_document_status",
            "company_id",
            "currency",
            "document_status",
        ),
        Index(
            "ix_sale_records_provider_external_updated_at",
            "provider",
            "external_updated_at",
        ),
        CheckConstraint(
            "gross_amount_minor >= 0",
            name="ck_sale_records_gross_amount_non_negative",
        ),
        CheckConstraint(
            "amount_sign IN (1, -1)",
            name="ck_sale_records_amount_sign_valid",
        ),
        CheckConstraint(
            "currency_scale >= 0",
            name="ck_sale_records_currency_scale_non_negative",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    integration_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    import_batch_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_key: Mapped[str] = mapped_column(String(512), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    erp_document_type: Mapped[str | None] = mapped_column(String(120))
    document_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    external_document_id: Mapped[str | None] = mapped_column(String(255))
    external_document_number: Mapped[str | None] = mapped_column(String(255))
    external_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    net_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    vat_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    discount_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    paid_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    debt_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    amount_sign: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    currency_scale: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(32),
        default=PaymentStatus.UNKNOWN.value,
        nullable=False,
    )
    document_status: Mapped[str] = mapped_column(
        String(32),
        default=SaleDocumentStatus.UNKNOWN.value,
        nullable=False,
    )
    is_deleted_in_source: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_archived_in_source: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    source_customer_external_id: Mapped[str | None] = mapped_column(String(255))
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    content_hash: Mapped[str | None] = mapped_column(String(128))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship()
    customer: Mapped[Customer] = relationship()


SaleProvider = ExternalProvider
