"""companies users auth billing foundation

Revision ID: 0001_companies_users_auth_billing
Revises:
Create Date: 2026-05-01 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_companies_users_auth_billing"
down_revision: str | None = None
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
    ]


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
        sa.UniqueConstraint("slug", name="uq_companies_slug"),
    )
    op.create_index("ix_companies_status", "companies", ["status"])

    op.create_table(
        "plans",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("limits_json", sa.JSON(), nullable=False),
        sa.Column("features_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
        sa.UniqueConstraint("code", name="uq_plans_code"),
    )

    op.create_table(
        "company_settings",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_year_start_month", sa.Integer(), nullable=False),
        sa.Column("fiscal_year_start_day", sa.Integer(), nullable=False),
        sa.Column("default_campaign_duration_days", sa.Integer(), nullable=True),
        sa.Column("default_campaign_rules_json", sa.JSON(), nullable=False),
        sa.Column("customer_portal_branding_json", sa.JSON(), nullable=False),
        sa.Column("sync_frequency_minutes", sa.Integer(), nullable=True),
        sa.Column("notification_preferences_json", sa.JSON(), nullable=False),
        sa.Column("reward_claim_enabled_default", sa.Boolean(), nullable=False),
        sa.Column("data_retention_days", sa.Integer(), nullable=True),
        sa.Column("extra_settings_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_company_settings_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_settings")),
        sa.UniqueConstraint("company_id", name="uq_company_settings_company_id"),
    )

    op.create_table(
        "users",
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_users_company_id_companies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_company_id", "users", ["company_id"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "company_subscriptions",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trial_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "current_period_starts_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("current_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_company_subscriptions_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            name=op.f("fk_company_subscriptions_plan_id_plans"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_subscriptions")),
    )
    op.create_index(
        "ix_company_subscriptions_company_id",
        "company_subscriptions",
        ["company_id"],
    )
    op.create_index(
        "ix_company_subscriptions_plan_id",
        "company_subscriptions",
        ["plan_id"],
    )
    op.create_index(
        "ix_company_subscriptions_status",
        "company_subscriptions",
        ["status"],
    )

    op.create_table(
        "company_usage_limits",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("limit_key", sa.String(length=120), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_company_usage_limits_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_usage_limits")),
        sa.UniqueConstraint(
            "company_id",
            "limit_key",
            name="uq_company_usage_limits_company_id_limit_key",
        ),
    )
    op.create_index(
        "ix_company_usage_limits_company_id",
        "company_usage_limits",
        ["company_id"],
    )

    op.create_table(
        "usage_counters",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("metric", sa.String(length=120), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_usage_counters_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_counters")),
        sa.UniqueConstraint(
            "company_id",
            "metric",
            "period_start",
            "period_end",
            name="uq_usage_counters_company_metric_period",
        ),
    )
    op.create_index("ix_usage_counters_company_id", "usage_counters", ["company_id"])

    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint(
            "refresh_token_hash",
            name="uq_user_sessions_refresh_token_hash",
        ),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_usage_counters_company_id", table_name="usage_counters")
    op.drop_table("usage_counters")
    op.drop_index(
        "ix_company_usage_limits_company_id",
        table_name="company_usage_limits",
    )
    op.drop_table("company_usage_limits")
    op.drop_index(
        "ix_company_subscriptions_status",
        table_name="company_subscriptions",
    )
    op.drop_index(
        "ix_company_subscriptions_plan_id",
        table_name="company_subscriptions",
    )
    op.drop_index(
        "ix_company_subscriptions_company_id",
        table_name="company_subscriptions",
    )
    op.drop_table("company_subscriptions")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_company_id", table_name="users")
    op.drop_table("users")
    op.drop_table("company_settings")
    op.drop_table("plans")
    op.drop_index("ix_companies_status", table_name="companies")
    op.drop_table("companies")
