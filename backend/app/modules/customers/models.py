from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company
from app.modules.users.models import User


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    BLOCKED = "blocked"


class ExternalProvider(StrEnum):
    FAKE = "fake"
    MOYSKLAD = "moysklad"
    CSV = "csv"
    MANUAL = "manual"
    CUSTOM_API = "custom_api"
    ONE_C = "one_c"
    ODOO = "odoo"
    ERPNEXT = "erpnext"


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_company_id", "company_id"),
        Index("ix_customers_company_id_status", "company_id", "status"),
        Index("ix_customers_company_id_phone", "company_id", "phone"),
        Index("ix_customers_company_id_email", "company_id", "email"),
        Index("ix_customers_company_id_tax_id", "company_id", "tax_id"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(320))
    tax_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(32),
        default=CustomerStatus.ACTIVE.value,
        nullable=False,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    company: Mapped[Company] = relationship()


class CustomerExternalRef(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_external_refs"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "provider",
            "external_id",
            name="uq_customer_external_refs_company_provider_external_id",
        ),
        Index("ix_customer_external_refs_customer_id", "customer_id"),
        Index(
            "ix_customer_external_refs_company_provider_external_id",
            "company_id",
            "provider",
            "external_id",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    integration_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_name: Mapped[str | None] = mapped_column(String(255))
    external_phone: Mapped[str | None] = mapped_column(String(64))
    external_email: Mapped[str | None] = mapped_column(String(320))
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship()
    customer: Mapped[Customer] = relationship()


class CustomerAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_assignments"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "customer_id",
            "sales_manager_user_id",
            name="uq_customer_assignments_company_customer_sales_manager",
        ),
        Index("ix_customer_assignments_sales_manager_user_id", "sales_manager_user_id"),
        Index("ix_customer_assignments_customer_id", "customer_id"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    sales_manager_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    company: Mapped[Company] = relationship()
    customer: Mapped[Customer] = relationship()
    sales_manager: Mapped[User] = relationship()
