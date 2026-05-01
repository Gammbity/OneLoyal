"""customers and sale records

Revision ID: 0003_customers_sales
Revises: 0002_campaigns_gift_tiers
Create Date: 2026-05-01 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_customers_sales"
down_revision: str | None = "0002_campaigns_gift_tiers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns(*, soft_delete: bool = False) -> list[sa.Column]:
    columns = [
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
    if soft_delete:
        columns.append(sa.Column("deleted_at", sa.DateTime(timezone=True)))
    return columns


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("tax_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(soft_delete=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_customers_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index("ix_customers_company_id", "customers", ["company_id"])
    op.create_index(
        "ix_customers_company_id_status",
        "customers",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_customers_company_id_phone",
        "customers",
        ["company_id", "phone"],
    )
    op.create_index(
        "ix_customers_company_id_email",
        "customers",
        ["company_id", "email"],
    )
    op.create_index(
        "ix_customers_company_id_tax_id",
        "customers",
        ["company_id", "tax_id"],
    )

    op.create_table(
        "customer_external_refs",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("external_name", sa.String(length=255), nullable=True),
        sa.Column("external_phone", sa.String(length=64), nullable=True),
        sa.Column("external_email", sa.String(length=320), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_customer_external_refs_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_customer_external_refs_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_external_refs")),
        sa.UniqueConstraint(
            "company_id",
            "provider",
            "external_id",
            name="uq_customer_external_refs_company_provider_external_id",
        ),
    )
    op.create_index(
        "ix_customer_external_refs_customer_id",
        "customer_external_refs",
        ["customer_id"],
    )
    op.create_index(
        "ix_customer_external_refs_company_provider_external_id",
        "customer_external_refs",
        ["company_id", "provider", "external_id"],
    )

    op.create_table(
        "customer_assignments",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("sales_manager_user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_customer_assignments_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_customer_assignments_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sales_manager_user_id"],
            ["users.id"],
            name=op.f("fk_customer_assignments_sales_manager_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_assignments")),
        sa.UniqueConstraint(
            "company_id",
            "customer_id",
            "sales_manager_user_id",
            name="uq_customer_assignments_company_customer_sales_manager",
        ),
    )
    op.create_index(
        "ix_customer_assignments_sales_manager_user_id",
        "customer_assignments",
        ["sales_manager_user_id"],
    )
    op.create_index(
        "ix_customer_assignments_customer_id",
        "customer_assignments",
        ["customer_id"],
    )

    op.create_table(
        "sale_records",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("integration_id", sa.Uuid(), nullable=True),
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_key", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("erp_document_type", sa.String(length=120), nullable=True),
        sa.Column("document_kind", sa.String(length=32), nullable=False),
        sa.Column("external_document_id", sa.String(length=255), nullable=True),
        sa.Column("external_document_number", sa.String(length=255), nullable=True),
        sa.Column("external_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("gross_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("net_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("vat_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("discount_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("paid_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("debt_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("amount_sign", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("currency_scale", sa.Integer(), nullable=False),
        sa.Column("payment_status", sa.String(length=32), nullable=False),
        sa.Column("document_status", sa.String(length=32), nullable=False),
        sa.Column("is_deleted_in_source", sa.Boolean(), nullable=False),
        sa.Column("is_archived_in_source", sa.Boolean(), nullable=False),
        sa.Column("source_customer_external_id", sa.String(length=255), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(soft_delete=True),
        sa.CheckConstraint(
            "gross_amount_minor >= 0",
            name="ck_sale_records_gross_amount_non_negative",
        ),
        sa.CheckConstraint(
            "amount_sign IN (1, -1)",
            name="ck_sale_records_amount_sign_valid",
        ),
        sa.CheckConstraint(
            "currency_scale >= 0",
            name="ck_sale_records_currency_scale_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_sale_records_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_sale_records_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sale_records")),
        sa.UniqueConstraint(
            "company_id",
            "source_key",
            name="uq_sale_records_source_key",
        ),
    )
    op.create_index("ix_sale_records_company_id", "sale_records", ["company_id"])
    op.create_index("ix_sale_records_customer_id", "sale_records", ["customer_id"])
    op.create_index(
        "ix_sale_records_company_customer_effective_date",
        "sale_records",
        ["company_id", "customer_id", "effective_date"],
    )
    op.create_index(
        "ix_sale_records_company_effective_date",
        "sale_records",
        ["company_id", "effective_date"],
    )
    op.create_index(
        "ix_sale_records_company_currency_document_status",
        "sale_records",
        ["company_id", "currency", "document_status"],
    )
    op.create_index(
        "ix_sale_records_provider_external_updated_at",
        "sale_records",
        ["provider", "external_updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sale_records_provider_external_updated_at",
        table_name="sale_records",
    )
    op.drop_index(
        "ix_sale_records_company_currency_document_status",
        table_name="sale_records",
    )
    op.drop_index(
        "ix_sale_records_company_effective_date",
        table_name="sale_records",
    )
    op.drop_index(
        "ix_sale_records_company_customer_effective_date",
        table_name="sale_records",
    )
    op.drop_index("ix_sale_records_customer_id", table_name="sale_records")
    op.drop_index("ix_sale_records_company_id", table_name="sale_records")
    op.drop_table("sale_records")
    op.drop_index(
        "ix_customer_assignments_customer_id",
        table_name="customer_assignments",
    )
    op.drop_index(
        "ix_customer_assignments_sales_manager_user_id",
        table_name="customer_assignments",
    )
    op.drop_table("customer_assignments")
    op.drop_index(
        "ix_customer_external_refs_company_provider_external_id",
        table_name="customer_external_refs",
    )
    op.drop_index(
        "ix_customer_external_refs_customer_id",
        table_name="customer_external_refs",
    )
    op.drop_table("customer_external_refs")
    op.drop_index("ix_customers_company_id_tax_id", table_name="customers")
    op.drop_index("ix_customers_company_id_email", table_name="customers")
    op.drop_index("ix_customers_company_id_phone", table_name="customers")
    op.drop_index("ix_customers_company_id_status", table_name="customers")
    op.drop_index("ix_customers_company_id", table_name="customers")
    op.drop_table("customers")

