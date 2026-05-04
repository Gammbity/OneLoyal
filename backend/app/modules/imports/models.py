from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company
from app.modules.users.models import User


class ImportBatchStatus(StrEnum):
    DRAFT = "draft"
    PREVIEWED = "previewed"
    COMMITTED = "committed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImportRowStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    COMMITTED = "committed"
    SKIPPED = "skipped"


class ImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        Index("ix_import_batches_company_id", "company_id"),
        Index("ix_import_batches_status", "status"),
        Index("ix_import_batches_created_at", "created_at"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    source_type: Mapped[str] = mapped_column(String(32), default="csv", nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default="csv", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ImportBatchStatus.DRAFT.value,
        nullable=False,
    )
    original_filename: Mapped[str | None] = mapped_column(String(255))
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    committed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stats_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    error_summary: Mapped[str | None] = mapped_column(Text)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship()
    created_by: Mapped[User | None] = relationship()
    rows: Mapped[list["ImportRow"]] = relationship(
        back_populates="import_batch",
        cascade="all, delete-orphan",
    )


class ImportRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_rows"
    __table_args__ = (
        Index("ix_import_rows_company_id", "company_id"),
        Index("ix_import_rows_import_batch_id", "import_batch_id"),
        Index("ix_import_rows_status", "status"),
        Index("ix_import_rows_idempotency_key", "idempotency_key"),
        Index(
            "uq_import_rows_import_batch_row_number",
            "import_batch_id",
            "row_number",
            unique=True,
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    import_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_row_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    normalized_row_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_messages_json: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    customer_external_id: Mapped[str | None] = mapped_column(String(255))
    sale_external_id: Mapped[str | None] = mapped_column(String(255))

    company: Mapped[Company] = relationship()
    import_batch: Mapped[ImportBatch] = relationship(back_populates="rows")
