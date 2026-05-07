from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company
from app.modules.customers.models import Customer
from app.modules.events.models import DomainEvent
from app.modules.users.models import User


class NotificationChannel(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationRecipientType(StrEnum):
    CUSTOMER = "customer"
    COMPANY_ADMIN = "company_admin"
    SALES_MANAGER = "sales_manager"


class NotificationEventStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class NotificationTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_templates"
    __table_args__ = (
        Index("ix_notification_templates_company_id", "company_id"),
        Index("ix_notification_templates_company_channel", "company_id", "channel"),
        Index("ix_notification_templates_company_active", "company_id", "is_active"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_template: Mapped[str | None] = mapped_column(String(500))
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    company: Mapped[Company] = relationship()


class NotificationRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_rules"
    __table_args__ = (
        Index("ix_notification_rules_company_id", "company_id"),
        Index("ix_notification_rules_company_event_type", "company_id", "event_type"),
        Index("ix_notification_rules_template_id", "template_id"),
        Index("ix_notification_rules_company_active", "company_id", "is_active"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    company: Mapped[Company] = relationship()
    template: Mapped[NotificationTemplate] = relationship()


class NotificationEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_events"
    __table_args__ = (
        Index("ix_notification_events_company_id", "company_id"),
        Index("ix_notification_events_domain_event_id", "domain_event_id"),
        Index("ix_notification_events_rule_id", "notification_rule_id"),
        Index("ix_notification_events_status_created_at", "status", "created_at"),
        Index("ix_notification_events_customer_id", "customer_id"),
        Index("ix_notification_events_user_id", "user_id"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    domain_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("domain_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    notification_rule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("notification_rules.id", ondelete="SET NULL")
    )
    notification_template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("notification_templates.id", ondelete="SET NULL")
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL")
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    recipient_identifier: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32),
        default=NotificationEventStatus.PENDING.value,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    skipped_reason: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship()
    domain_event: Mapped[DomainEvent] = relationship()
    notification_rule: Mapped[NotificationRule | None] = relationship()
    notification_template: Mapped[NotificationTemplate | None] = relationship()
    customer: Mapped[Customer | None] = relationship()
    user: Mapped[User | None] = relationship()
