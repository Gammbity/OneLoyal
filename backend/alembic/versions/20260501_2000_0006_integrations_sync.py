"""integrations and sync runs

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-01 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
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
        "integrations",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("last_attempted_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_cursor_json", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_integrations_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integrations")),
    )
    op.create_index("ix_integrations_company_id", "integrations", ["company_id"])
    op.create_index(
        "ix_integrations_company_id_provider",
        "integrations",
        ["company_id", "provider"],
    )
    op.create_index(
        "ix_integrations_company_id_status",
        "integrations",
        ["company_id", "status"],
    )

    op.create_table(
        "integration_credentials",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_integration_credentials_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["integration_id"],
            ["integrations.id"],
            name=op.f("fk_integration_credentials_integration_id_integrations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_credentials")),
    )
    op.create_index(
        "ix_integration_credentials_company_id",
        "integration_credentials",
        ["company_id"],
    )
    op.create_index(
        "ix_integration_credentials_integration_id",
        "integration_credentials",
        ["integration_id"],
    )
    op.create_index(
        "ix_integration_credentials_integration_active",
        "integration_credentials",
        ["integration_id", "is_active"],
    )

    op.create_table(
        "sync_runs",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=False),
        sa.Column("sync_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor_before_json", sa.JSON(), nullable=False),
        sa.Column("cursor_after_json", sa.JSON(), nullable=False),
        sa.Column("stats_json", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_sync_runs_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_sync_runs_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["integration_id"],
            ["integrations.id"],
            name=op.f("fk_sync_runs_integration_id_integrations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_runs")),
    )
    op.create_index("ix_sync_runs_company_id", "sync_runs", ["company_id"])
    op.create_index("ix_sync_runs_integration_id", "sync_runs", ["integration_id"])
    op.create_index("ix_sync_runs_status", "sync_runs", ["status"])
    op.create_index("ix_sync_runs_started_at", "sync_runs", ["started_at"])

    op.create_table(
        "sync_errors",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_sync_errors_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sync_run_id"],
            ["sync_runs.id"],
            name=op.f("fk_sync_errors_sync_run_id_sync_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_errors")),
    )
    op.create_index("ix_sync_errors_company_id", "sync_errors", ["company_id"])
    op.create_index("ix_sync_errors_sync_run_id", "sync_errors", ["sync_run_id"])
    op.create_index("ix_sync_errors_entity_type", "sync_errors", ["entity_type"])
    op.create_index("ix_sync_errors_external_id", "sync_errors", ["external_id"])


def downgrade() -> None:
    op.drop_index("ix_sync_errors_external_id", table_name="sync_errors")
    op.drop_index("ix_sync_errors_entity_type", table_name="sync_errors")
    op.drop_index("ix_sync_errors_sync_run_id", table_name="sync_errors")
    op.drop_index("ix_sync_errors_company_id", table_name="sync_errors")
    op.drop_table("sync_errors")

    op.drop_index("ix_sync_runs_started_at", table_name="sync_runs")
    op.drop_index("ix_sync_runs_status", table_name="sync_runs")
    op.drop_index("ix_sync_runs_integration_id", table_name="sync_runs")
    op.drop_index("ix_sync_runs_company_id", table_name="sync_runs")
    op.drop_table("sync_runs")

    op.drop_index(
        "ix_integration_credentials_integration_active",
        table_name="integration_credentials",
    )
    op.drop_index(
        "ix_integration_credentials_integration_id",
        table_name="integration_credentials",
    )
    op.drop_index(
        "ix_integration_credentials_company_id",
        table_name="integration_credentials",
    )
    op.drop_table("integration_credentials")

    op.drop_index("ix_integrations_company_id_status", table_name="integrations")
    op.drop_index("ix_integrations_company_id_provider", table_name="integrations")
    op.drop_index("ix_integrations_company_id", table_name="integrations")
    op.drop_table("integrations")
