from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.companies.models import Company
from app.modules.customers.models import Customer
from app.modules.users.models import User


class MagicLinkToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "magic_link_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_magic_link_tokens_token_hash"),
        Index("ix_magic_link_tokens_company_id", "company_id"),
        Index("ix_magic_link_tokens_customer_id", "customer_id"),
        Index("ix_magic_link_tokens_expires_at", "expires_at"),
        Index("ix_magic_link_tokens_revoked_at", "revoked_at"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    company: Mapped[Company] = relationship()
    customer: Mapped[Customer] = relationship()
    created_by: Mapped[User | None] = relationship()
