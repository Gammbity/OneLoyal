"""async sync scheduling fields

Revision ID: 0008_async_sync_scheduling
Revises: 0007_import_batches
Create Date: 2026-05-04 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_async_sync_scheduling"
down_revision: str | None = "0007_import_batches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "integrations",
        sa.Column("last_scheduled_sync_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "integrations",
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_integrations_next_sync_at",
        "integrations",
        ["next_sync_at"],
    )

    op.add_column(
        "sync_runs",
        sa.Column("task_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "sync_runs",
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "sync_runs",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.create_index("ix_sync_runs_task_id", "sync_runs", ["task_id"])
    op.create_index("ix_sync_runs_enqueued_at", "sync_runs", ["enqueued_at"])


def downgrade() -> None:
    op.drop_index("ix_sync_runs_enqueued_at", table_name="sync_runs")
    op.drop_index("ix_sync_runs_task_id", table_name="sync_runs")
    op.alter_column(
        "sync_runs",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_column("sync_runs", "enqueued_at")
    op.drop_column("sync_runs", "task_id")

    op.drop_index("ix_integrations_next_sync_at", table_name="integrations")
    op.drop_column("integrations", "next_sync_at")
    op.drop_column("integrations", "last_scheduled_sync_at")
