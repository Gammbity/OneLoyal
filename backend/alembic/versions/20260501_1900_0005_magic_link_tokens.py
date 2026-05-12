"""magic link tokens

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-01 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "magic_link_tokens",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_magic_link_tokens_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_magic_link_tokens_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_magic_link_tokens_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_magic_link_tokens")),
        sa.UniqueConstraint("token_hash", name="uq_magic_link_tokens_token_hash"),
    )
    op.create_index(
        "ix_magic_link_tokens_company_id",
        "magic_link_tokens",
        ["company_id"],
    )
    op.create_index(
        "ix_magic_link_tokens_customer_id",
        "magic_link_tokens",
        ["customer_id"],
    )
    op.create_index(
        "ix_magic_link_tokens_expires_at",
        "magic_link_tokens",
        ["expires_at"],
    )
    op.create_index(
        "ix_magic_link_tokens_revoked_at",
        "magic_link_tokens",
        ["revoked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_magic_link_tokens_revoked_at", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_expires_at", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_customer_id", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_company_id", table_name="magic_link_tokens")
    op.drop_table("magic_link_tokens")
