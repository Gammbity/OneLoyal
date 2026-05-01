from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Plan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plans"
    __table_args__ = (UniqueConstraint("code", name="uq_plans_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    limits_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    features_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CompanySubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "company_subscriptions"
    __table_args__ = (
        Index("ix_company_subscriptions_company_id", "company_id"),
        Index("ix_company_subscriptions_plan_id", "plan_id"),
        Index("ix_company_subscriptions_status", "status"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trial_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    current_period_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    company: Mapped[Company] = relationship()
    plan: Mapped[Plan] = relationship()


class CompanyUsageLimit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "company_usage_limits"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "limit_key",
            name="uq_company_usage_limits_company_id_limit_key",
        ),
        Index("ix_company_usage_limits_company_id", "company_id"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    limit_key: Mapped[str] = mapped_column(String(120), nullable=False)
    limit_value: Mapped[int | None] = mapped_column(Integer)

    company: Mapped[Company] = relationship()


class UsageCounter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "metric",
            "period_start",
            "period_end",
            name="uq_usage_counters_company_metric_period",
        ),
        Index("ix_usage_counters_company_id", "company_id"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric: Mapped[str] = mapped_column(String(120), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    company: Mapped[Company] = relationship()
