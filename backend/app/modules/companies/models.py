from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CompanyStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_companies_slug"),
        Index("ix_companies_slug", "slug"),
        Index("ix_companies_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=CompanyStatus.ACTIVE.value,
        nullable=False,
    )
    base_currency: Mapped[str] = mapped_column(String(3), default="UZS", nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="Asia/Tashkent",
        nullable=False,
    )

    settings: Mapped["CompanySettings"] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        uselist=False,
    )


class CompanySettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "company_settings"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_settings_company_id"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, default=1)
    fiscal_year_start_day: Mapped[int] = mapped_column(Integer, default=1)
    default_campaign_duration_days: Mapped[int | None] = mapped_column(Integer)
    default_campaign_rules_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    customer_portal_branding_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    sync_frequency_minutes: Mapped[int | None] = mapped_column(Integer)
    notification_preferences_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    reward_claim_enabled_default: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    data_retention_days: Mapped[int | None] = mapped_column(Integer)
    extra_settings_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    company: Mapped[Company] = relationship(back_populates="settings")
