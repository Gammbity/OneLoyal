"""customer campaign progress

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-01 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_campaign_progress",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("total_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("current_tier_id", sa.Uuid(), nullable=True),
        sa.Column("next_tier_id", sa.Uuid(), nullable=True),
        sa.Column("amount_left_minor", sa.BigInteger(), nullable=False),
        sa.Column("progress_percent_basis_points", sa.Integer(), nullable=False),
        sa.Column("calculation_version", sa.Integer(), nullable=False),
        sa.Column("stats_json", sa.JSON(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
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
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_customer_campaign_progress_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_customer_campaign_progress_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["current_tier_id"],
            ["gift_tiers.id"],
            name=op.f("fk_customer_campaign_progress_current_tier_id_gift_tiers"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_customer_campaign_progress_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["next_tier_id"],
            ["gift_tiers.id"],
            name=op.f("fk_customer_campaign_progress_next_tier_id_gift_tiers"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_campaign_progress")),
        sa.UniqueConstraint(
            "company_id",
            "campaign_id",
            "customer_id",
            name="uq_customer_campaign_progress_company_campaign_customer",
        ),
    )
    op.create_index(
        "ix_customer_campaign_progress_campaign_id",
        "customer_campaign_progress",
        ["campaign_id"],
    )
    op.create_index(
        "ix_customer_campaign_progress_company_campaign",
        "customer_campaign_progress",
        ["company_id", "campaign_id"],
    )
    op.create_index(
        "ix_customer_campaign_progress_company_customer",
        "customer_campaign_progress",
        ["company_id", "customer_id"],
    )
    op.create_index(
        "ix_customer_campaign_progress_company_id",
        "customer_campaign_progress",
        ["company_id"],
    )
    op.create_index(
        "ix_customer_campaign_progress_customer_id",
        "customer_campaign_progress",
        ["customer_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_customer_campaign_progress_customer_id",
        table_name="customer_campaign_progress",
    )
    op.drop_index(
        "ix_customer_campaign_progress_company_id",
        table_name="customer_campaign_progress",
    )
    op.drop_index(
        "ix_customer_campaign_progress_company_customer",
        table_name="customer_campaign_progress",
    )
    op.drop_index(
        "ix_customer_campaign_progress_company_campaign",
        table_name="customer_campaign_progress",
    )
    op.drop_index(
        "ix_customer_campaign_progress_campaign_id",
        table_name="customer_campaign_progress",
    )
    op.drop_table("customer_campaign_progress")

