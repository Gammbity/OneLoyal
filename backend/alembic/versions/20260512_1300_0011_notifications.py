"""notifications tables

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-12 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        "notification_templates",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("subject_template", sa.String(length=500), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_notification_templates_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_templates")),
    )
    op.create_index(
        "ix_notification_templates_company_id",
        "notification_templates",
        ["company_id"],
    )
    op.create_index(
        "ix_notification_templates_company_channel",
        "notification_templates",
        ["company_id", "channel"],
    )
    op.create_index(
        "ix_notification_templates_company_active",
        "notification_templates",
        ["company_id", "is_active"],
    )

    op.create_table(
        "notification_rules",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient_type", sa.String(length=32), nullable=False),
        sa.Column("condition_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_notification_rules_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["notification_templates.id"],
            name=op.f("fk_notification_rules_template_id_notification_templates"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_rules")),
    )
    op.create_index(
        "ix_notification_rules_company_id",
        "notification_rules",
        ["company_id"],
    )
    op.create_index(
        "ix_notification_rules_company_event_type",
        "notification_rules",
        ["company_id", "event_type"],
    )
    op.create_index(
        "ix_notification_rules_template_id",
        "notification_rules",
        ["template_id"],
    )
    op.create_index(
        "ix_notification_rules_company_active",
        "notification_rules",
        ["company_id", "is_active"],
    )

    op.create_table(
        "notification_events",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("domain_event_id", sa.Uuid(), nullable=False),
        sa.Column("notification_rule_id", sa.Uuid(), nullable=True),
        sa.Column("notification_template_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient_type", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_identifier", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("skipped_reason", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_notification_events_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["domain_event_id"],
            ["domain_events.id"],
            name=op.f("fk_notification_events_domain_event_id_domain_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["notification_rule_id"],
            ["notification_rules.id"],
            name=op.f("fk_notification_events_notification_rule_id_notification_rules"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["notification_template_id"],
            ["notification_templates.id"],
            name=op.f("fk_notification_events_notification_template_id_notification_templates"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_notification_events_customer_id_customers"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_events_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_events")),
    )
    op.create_index(
        "ix_notification_events_company_id",
        "notification_events",
        ["company_id"],
    )
    op.create_index(
        "ix_notification_events_domain_event_id",
        "notification_events",
        ["domain_event_id"],
    )
    op.create_index(
        "ix_notification_events_rule_id",
        "notification_events",
        ["notification_rule_id"],
    )
    op.create_index(
        "ix_notification_events_status_created_at",
        "notification_events",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_notification_events_customer_id",
        "notification_events",
        ["customer_id"],
    )
    op.create_index(
        "ix_notification_events_user_id",
        "notification_events",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_events_user_id", table_name="notification_events")
    op.drop_index(
        "ix_notification_events_customer_id",
        table_name="notification_events",
    )
    op.drop_index(
        "ix_notification_events_status_created_at",
        table_name="notification_events",
    )
    op.drop_index("ix_notification_events_rule_id", table_name="notification_events")
    op.drop_index(
        "ix_notification_events_domain_event_id",
        table_name="notification_events",
    )
    op.drop_index("ix_notification_events_company_id", table_name="notification_events")
    op.drop_table("notification_events")

    op.drop_index("ix_notification_rules_company_active", table_name="notification_rules")
    op.drop_index("ix_notification_rules_template_id", table_name="notification_rules")
    op.drop_index(
        "ix_notification_rules_company_event_type",
        table_name="notification_rules",
    )
    op.drop_index("ix_notification_rules_company_id", table_name="notification_rules")
    op.drop_table("notification_rules")

    op.drop_index(
        "ix_notification_templates_company_active",
        table_name="notification_templates",
    )
    op.drop_index(
        "ix_notification_templates_company_channel",
        table_name="notification_templates",
    )
    op.drop_index(
        "ix_notification_templates_company_id",
        table_name="notification_templates",
    )
    op.drop_table("notification_templates")
