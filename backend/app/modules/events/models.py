from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.datetime import utc_now
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DomainEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class DomainEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "domain_events"
    __table_args__ = (
        Index("ix_domain_events_company_id", "company_id"),
        Index("ix_domain_events_event_type", "event_type"),
        Index("ix_domain_events_aggregate_type_id", "aggregate_type", "aggregate_id"),
        Index("ix_domain_events_customer_id", "customer_id"),
        Index("ix_domain_events_campaign_id", "campaign_id"),
        Index("ix_domain_events_status_occurred_at", "status", "occurred_at"),
    )

    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL")
    )
    campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL")
    )
    gift_tier_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("gift_tiers.id", ondelete="SET NULL")
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL")
    )
    correlation_id: Mapped[str | None] = mapped_column(String(255))
    request_id: Mapped[str | None] = mapped_column(String(255))
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=DomainEventStatus.PENDING.value,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
