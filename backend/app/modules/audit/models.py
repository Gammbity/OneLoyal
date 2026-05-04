from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.datetime import utc_now
from app.db.base import Base, UUIDPrimaryKeyMixin


class AuditActorType(StrEnum):
    SYSTEM = "system"
    USER = "user"
    CUSTOMER = "customer"
    TASK = "task"


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_company_id", "company_id"),
        Index("ix_audit_logs_actor_user_id", "actor_user_id"),
        Index("ix_audit_logs_actor_customer_id", "actor_customer_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_entity_type_id", "entity_type", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL")
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL")
    )
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    request_id: Mapped[str | None] = mapped_column(String(255))
    before_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    after_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
