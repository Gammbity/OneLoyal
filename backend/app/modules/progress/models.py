from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.datetime import utc_now
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.campaigns.models import Campaign, GiftTier
from app.modules.companies.models import Company
from app.modules.customers.models import Customer


class CustomerCampaignProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_campaign_progress"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "campaign_id",
            "customer_id",
            name="uq_customer_campaign_progress_company_campaign_customer",
        ),
        Index("ix_customer_campaign_progress_company_id", "company_id"),
        Index("ix_customer_campaign_progress_campaign_id", "campaign_id"),
        Index("ix_customer_campaign_progress_customer_id", "customer_id"),
        Index(
            "ix_customer_campaign_progress_company_campaign",
            "company_id",
            "campaign_id",
        ),
        Index(
            "ix_customer_campaign_progress_company_customer",
            "company_id",
            "customer_id",
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
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    total_amount_minor: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    current_tier_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("gift_tiers.id", ondelete="SET NULL")
    )
    next_tier_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("gift_tiers.id", ondelete="SET NULL")
    )
    amount_left_minor: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    progress_percent_basis_points: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    calculation_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    stats_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    company: Mapped[Company] = relationship()
    campaign: Mapped[Campaign] = relationship()
    customer: Mapped[Customer] = relationship()
    current_tier: Mapped[GiftTier | None] = relationship(
        foreign_keys=[current_tier_id],
    )
    next_tier: Mapped[GiftTier | None] = relationship(foreign_keys=[next_tier_id])

    @property
    def progress_percent(self) -> Decimal:
        return Decimal(self.progress_percent_basis_points) / Decimal("100")

    @property
    def customer_name(self) -> str | None:
        return self.customer.name if self.customer is not None else None

    @property
    def current_tier_title(self) -> str | None:
        return self.current_tier.title if self.current_tier is not None else None

    @property
    def next_tier_title(self) -> str | None:
        return self.next_tier.title if self.next_tier is not None else None

