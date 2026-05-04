from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company
from app.modules.integrations.models import Integration
from app.modules.users.models import User


class SyncType(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    FULL = "full"
    INCREMENTAL = "incremental"


class SyncRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIALLY_FAILED = "partially_failed"


class SyncErrorEntityType(StrEnum):
    CUSTOMER = "customer"
    SALE_RECORD = "sale_record"
    PROVIDER = "provider"
    PROGRESS = "progress"
    UNKNOWN = "unknown"


class SyncErrorSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class SyncRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        Index("ix_sync_runs_company_id", "company_id"),
        Index("ix_sync_runs_integration_id", "integration_id"),
        Index("ix_sync_runs_status", "status"),
        Index("ix_sync_runs_task_id", "task_id"),
        Index("ix_sync_runs_enqueued_at", "enqueued_at"),
        Index("ix_sync_runs_started_at", "started_at"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    integration_id: Mapped[UUID] = mapped_column(
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=SyncRunStatus.QUEUED.value,
        nullable=False,
    )
    task_id: Mapped[str | None] = mapped_column(String(255))
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cursor_before_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    cursor_after_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    stats_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    company: Mapped[Company] = relationship()
    integration: Mapped[Integration] = relationship()
    created_by: Mapped[User | None] = relationship()
    errors: Mapped[list["SyncError"]] = relationship(
        back_populates="sync_run",
        cascade="all, delete-orphan",
    )


class SyncError(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sync_errors"
    __table_args__ = (
        Index("ix_sync_errors_company_id", "company_id"),
        Index("ix_sync_errors_sync_run_id", "sync_run_id"),
        Index("ix_sync_errors_entity_type", "entity_type"),
        Index("ix_sync_errors_external_id", "external_id"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    company: Mapped[Company] = relationship()
    sync_run: Mapped[SyncRun] = relationship(back_populates="errors")
