from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class StockTrackingMode(StrEnum):
    NONE = "none"
    SOFT = "soft"
    STRICT = "strict"


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        Index("ix_campaigns_company_id", "company_id"),
        Index("ix_campaigns_company_id_status", "company_id", "status"),
        Index(
            "ix_campaigns_company_id_start_date_end_date",
            "company_id",
            "start_date",
            "end_date",
        ),
        CheckConstraint("end_date >= start_date", name="ck_campaigns_date_range"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # i18n translation maps: {"en": "...", "uz": "..."}
    title_i18n: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    description_i18n: Mapped[dict[str, str] | None] = mapped_column(JSON)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=CampaignStatus.DRAFT.value,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rules_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    visibility_settings_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    allow_claims: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped[Company] = relationship()
    gift_tiers: Mapped[list["GiftTier"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class GiftTier(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "gift_tiers"
    __table_args__ = (
        Index("ix_gift_tiers_company_id", "company_id"),
        Index("ix_gift_tiers_campaign_id", "campaign_id"),
        Index("ix_gift_tiers_campaign_id_sort_order", "campaign_id", "sort_order"),
        CheckConstraint(
            "required_amount_minor > 0",
            name="ck_gift_tiers_required_amount_positive",
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="ck_gift_tiers_reserved_quantity_non_negative",
        ),
        CheckConstraint(
            "fulfilled_quantity >= 0",
            name="ck_gift_tiers_fulfilled_quantity_non_negative",
        ),
        CheckConstraint(
            "stock_quantity IS NULL OR stock_quantity >= 0",
            name="ck_gift_tiers_stock_quantity_non_negative",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # i18n translation maps
    title_i18n: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    description_i18n: Mapped[dict[str, str] | None] = mapped_column(JSON)
    required_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    stock_tracking_mode: Mapped[str] = mapped_column(
        String(32),
        default=StockTrackingMode.NONE.value,
        nullable=False,
    )
    stock_quantity: Mapped[int | None] = mapped_column(Integer)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fulfilled_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped[Company] = relationship()
    campaign: Mapped[Campaign] = relationship(back_populates="gift_tiers")

    @property
    def available_quantity(self) -> int | None:
        if self.stock_quantity is None:
            return None
        return self.stock_quantity - self.reserved_quantity - self.fulfilled_quantity

