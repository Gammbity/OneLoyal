"""campaigns and gift tiers

Revision ID: 0002_campaigns_gift_tiers
Revises: 0001_companies_users_auth_billing
Create Date: 2026-05-01 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_campaigns_gift_tiers"
down_revision: str | None = "0001_companies_users_auth_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column("visibility_settings_json", sa.JSON(), nullable=False),
        sa.Column("allow_claims", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("end_date >= start_date", name="ck_campaigns_date_range"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_campaigns_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns")),
    )
    op.create_index("ix_campaigns_company_id", "campaigns", ["company_id"])
    op.create_index(
        "ix_campaigns_company_id_status",
        "campaigns",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_campaigns_company_id_start_date_end_date",
        "campaigns",
        ["company_id", "start_date", "end_date"],
    )

    op.create_table(
        "gift_tiers",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("required_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("stock_tracking_mode", sa.String(length=32), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), nullable=True),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False),
        sa.Column("fulfilled_quantity", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "required_amount_minor > 0",
            name="ck_gift_tiers_required_amount_positive",
        ),
        sa.CheckConstraint(
            "reserved_quantity >= 0",
            name="ck_gift_tiers_reserved_quantity_non_negative",
        ),
        sa.CheckConstraint(
            "fulfilled_quantity >= 0",
            name="ck_gift_tiers_fulfilled_quantity_non_negative",
        ),
        sa.CheckConstraint(
            "stock_quantity IS NULL OR stock_quantity >= 0",
            name="ck_gift_tiers_stock_quantity_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_gift_tiers_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_gift_tiers_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gift_tiers")),
    )
    op.create_index("ix_gift_tiers_company_id", "gift_tiers", ["company_id"])
    op.create_index("ix_gift_tiers_campaign_id", "gift_tiers", ["campaign_id"])
    op.create_index(
        "ix_gift_tiers_campaign_id_sort_order",
        "gift_tiers",
        ["campaign_id", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index("ix_gift_tiers_campaign_id_sort_order", table_name="gift_tiers")
    op.drop_index("ix_gift_tiers_campaign_id", table_name="gift_tiers")
    op.drop_index("ix_gift_tiers_company_id", table_name="gift_tiers")
    op.drop_table("gift_tiers")
    op.drop_index(
        "ix_campaigns_company_id_start_date_end_date",
        table_name="campaigns",
    )
    op.drop_index("ix_campaigns_company_id_status", table_name="campaigns")
    op.drop_index("ix_campaigns_company_id", table_name="campaigns")
    op.drop_table("campaigns")

