"""audit logs and domain events

Revision ID: 0010_audit_logs_domain_events
Revises: 0009_reward_claims
Create Date: 2026-05-04 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_audit_logs_domain_events"
down_revision: str | None = "0009_reward_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _timestamps() -> list[sa.Column]:
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
    ]


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_customer_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("before_json", sa.JSON(), nullable=False),
        sa.Column("after_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        _created_at_column(),
        sa.ForeignKeyConstraint(
            ["actor_customer_id"],
            ["customers.id"],
            name=op.f("fk_audit_logs_actor_customer_id_customers"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_audit_logs_company_id_companies"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_company_id", "audit_logs", ["company_id"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index(
        "ix_audit_logs_actor_customer_id",
        "audit_logs",
        ["actor_customer_id"],
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index(
        "ix_audit_logs_entity_type_id",
        "audit_logs",
        ["entity_type", "entity_id"],
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "domain_events",
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("gift_tier_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_customer_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["actor_customer_id"],
            ["customers.id"],
            name=op.f("fk_domain_events_actor_customer_id_customers"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_domain_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_domain_events_campaign_id_campaigns"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_domain_events_company_id_companies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_domain_events_customer_id_customers"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["gift_tier_id"],
            ["gift_tiers.id"],
            name=op.f("fk_domain_events_gift_tier_id_gift_tiers"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_domain_events")),
    )
    op.create_index("ix_domain_events_company_id", "domain_events", ["company_id"])
    op.create_index("ix_domain_events_event_type", "domain_events", ["event_type"])
    op.create_index(
        "ix_domain_events_aggregate_type_id",
        "domain_events",
        ["aggregate_type", "aggregate_id"],
    )
    op.create_index("ix_domain_events_customer_id", "domain_events", ["customer_id"])
    op.create_index("ix_domain_events_campaign_id", "domain_events", ["campaign_id"])
    op.create_index(
        "ix_domain_events_status_occurred_at",
        "domain_events",
        ["status", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_domain_events_status_occurred_at",
        table_name="domain_events",
    )
    op.drop_index("ix_domain_events_campaign_id", table_name="domain_events")
    op.drop_index("ix_domain_events_customer_id", table_name="domain_events")
    op.drop_index(
        "ix_domain_events_aggregate_type_id",
        table_name="domain_events",
    )
    op.drop_index("ix_domain_events_event_type", table_name="domain_events")
    op.drop_index("ix_domain_events_company_id", table_name="domain_events")
    op.drop_table("domain_events")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_customer_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_company_id", table_name="audit_logs")
    op.drop_table("audit_logs")
