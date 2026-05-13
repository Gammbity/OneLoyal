from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company


class IntegrationProvider(StrEnum):
    FAKE = "fake"
    MOYSKLAD = "moysklad"
    CSV = "csv"
    MANUAL = "manual"
    CUSTOM_API = "custom_api"
    ONE_C = "one_c"
    ODOO = "odoo"
    ERPNEXT = "erpnext"


class IntegrationStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class Integration(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "integrations"
    __table_args__ = (
        Index("ix_integrations_company_id", "company_id"),
        Index("ix_integrations_company_id_provider", "company_id", "provider"),
        Index("ix_integrations_company_id_status", "company_id", "status"),
        Index("ix_integrations_next_sync_at", "next_sync_at"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_i18n: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=IntegrationStatus.DRAFT.value,
        nullable=False,
    )
    settings_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    last_attempted_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_scheduled_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_cursor_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    company: Mapped[Company] = relationship()
    credentials: Mapped[list["IntegrationCredential"]] = relationship(
        back_populates="integration",
        cascade="all, delete-orphan",
    )


class IntegrationCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_credentials"
    __table_args__ = (
        Index("ix_integration_credentials_company_id", "company_id"),
        Index("ix_integration_credentials_integration_id", "integration_id"),
        Index(
            "ix_integration_credentials_integration_active",
            "integration_id",
            "is_active",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    integration_id: Mapped[UUID] = mapped_column(
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    credential_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship()
    integration: Mapped[Integration] = relationship(back_populates="credentials")
