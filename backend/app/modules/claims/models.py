from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.campaigns.models import Campaign, GiftTier
from app.modules.companies.models import Company
from app.modules.customers.models import Customer
from app.modules.users.models import User


class RewardClaimStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


ACTIVE_REWARD_CLAIM_STATUSES = {
    RewardClaimStatus.PENDING.value,
    RewardClaimStatus.APPROVED.value,
}


class RewardClaim(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "reward_claims"
    __table_args__ = (
        Index("ix_reward_claims_company_id", "company_id"),
        Index("ix_reward_claims_campaign_id", "campaign_id"),
        Index("ix_reward_claims_customer_id", "customer_id"),
        Index("ix_reward_claims_gift_tier_id", "gift_tier_id"),
        Index("ix_reward_claims_status", "status"),
        Index(
            "ix_reward_claims_company_campaign_customer",
            "company_id",
            "campaign_id",
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
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    gift_tier_id: Mapped[UUID] = mapped_column(
        ForeignKey("gift_tiers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=RewardClaimStatus.PENDING.value,
        nullable=False,
    )
    customer_comment: Mapped[str | None] = mapped_column(Text)
    admin_comment: Mapped[str | None] = mapped_column(Text)
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilled_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship()
    campaign: Mapped[Campaign] = relationship()
    customer: Mapped[Customer] = relationship()
    gift_tier: Mapped[GiftTier] = relationship()
    decided_by: Mapped[User | None] = relationship(foreign_keys=[decided_by_user_id])
    fulfilled_by: Mapped[User | None] = relationship(
        foreign_keys=[fulfilled_by_user_id],
    )
    cancelled_by: Mapped[User | None] = relationship(
        foreign_keys=[cancelled_by_user_id],
    )

    @property
    def customer_name(self) -> str | None:
        return self.customer.name if self.customer is not None else None

    @property
    def campaign_title(self) -> str | None:
        return self.campaign.title if self.campaign is not None else None

    @property
    def gift_tier_title(self) -> str | None:
        return self.gift_tier.title if self.gift_tier is not None else None
