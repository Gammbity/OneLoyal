"""reward claims

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-04 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
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
        "reward_claims",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("gift_tier_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("customer_comment", sa.Text(), nullable=True),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_reward_claims_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_user_id"],
            ["users.id"],
            name=op.f("fk_reward_claims_cancelled_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_reward_claims_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_reward_claims_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["users.id"],
            name=op.f("fk_reward_claims_decided_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fulfilled_by_user_id"],
            ["users.id"],
            name=op.f("fk_reward_claims_fulfilled_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["gift_tier_id"],
            ["gift_tiers.id"],
            name=op.f("fk_reward_claims_gift_tier_id_gift_tiers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reward_claims")),
    )
    op.create_index("ix_reward_claims_company_id", "reward_claims", ["company_id"])
    op.create_index("ix_reward_claims_campaign_id", "reward_claims", ["campaign_id"])
    op.create_index("ix_reward_claims_customer_id", "reward_claims", ["customer_id"])
    op.create_index(
        "ix_reward_claims_gift_tier_id",
        "reward_claims",
        ["gift_tier_id"],
    )
    op.create_index("ix_reward_claims_status", "reward_claims", ["status"])
    op.create_index(
        "ix_reward_claims_company_campaign_customer",
        "reward_claims",
        ["company_id", "campaign_id", "customer_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reward_claims_company_campaign_customer",
        table_name="reward_claims",
    )
    op.drop_index("ix_reward_claims_status", table_name="reward_claims")
    op.drop_index("ix_reward_claims_gift_tier_id", table_name="reward_claims")
    op.drop_index("ix_reward_claims_customer_id", table_name="reward_claims")
    op.drop_index("ix_reward_claims_campaign_id", table_name="reward_claims")
    op.drop_index("ix_reward_claims_company_id", table_name="reward_claims")
    op.drop_table("reward_claims")
