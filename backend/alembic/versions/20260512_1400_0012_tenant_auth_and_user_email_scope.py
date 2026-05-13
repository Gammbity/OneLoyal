"""tenant auth and user email scope

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-12 14:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_companies_slug", "companies", ["slug"], unique=False)
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.create_index(
        "ix_users_company_id_email",
        "users",
        ["company_id", "email"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_company_id_email", table_name="users")
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.drop_index("ix_companies_slug", table_name="companies")
