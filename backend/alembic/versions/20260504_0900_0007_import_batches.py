"""csv import batches

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-04 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
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
        "import_batches",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("committed_rows", sa.Integer(), nullable=False),
        sa.Column("skipped_rows", sa.Integer(), nullable=False),
        sa.Column("stats_json", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_import_batches_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_import_batches_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batches")),
    )
    op.create_index("ix_import_batches_company_id", "import_batches", ["company_id"])
    op.create_index("ix_import_batches_status", "import_batches", ["status"])
    op.create_index("ix_import_batches_created_at", "import_batches", ["created_at"])

    op.create_table(
        "import_rows",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_row_json", sa.JSON(), nullable=False),
        sa.Column("normalized_row_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_messages_json", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("customer_external_id", sa.String(length=255), nullable=True),
        sa.Column("sale_external_id", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_import_rows_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batches.id"],
            name=op.f("fk_import_rows_import_batch_id_import_batches"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_rows")),
        sa.UniqueConstraint(
            "import_batch_id",
            "row_number",
            name="uq_import_rows_import_batch_row_number",
        ),
    )
    op.create_index("ix_import_rows_company_id", "import_rows", ["company_id"])
    op.create_index(
        "ix_import_rows_import_batch_id",
        "import_rows",
        ["import_batch_id"],
    )
    op.create_index("ix_import_rows_status", "import_rows", ["status"])
    op.create_index(
        "ix_import_rows_idempotency_key",
        "import_rows",
        ["idempotency_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_import_rows_idempotency_key", table_name="import_rows")
    op.drop_index("ix_import_rows_status", table_name="import_rows")
    op.drop_index("ix_import_rows_import_batch_id", table_name="import_rows")
    op.drop_index("ix_import_rows_company_id", table_name="import_rows")
    op.drop_table("import_rows")
    op.drop_index("ix_import_batches_created_at", table_name="import_batches")
    op.drop_index("ix_import_batches_status", table_name="import_batches")
    op.drop_index("ix_import_batches_company_id", table_name="import_batches")
    op.drop_table("import_batches")
