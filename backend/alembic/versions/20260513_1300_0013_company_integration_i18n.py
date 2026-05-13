"""add i18n columns for companies and integrations

Revision ID: 20260513_1300_0013
Revises: 20260513_1200_0012
Create Date: 2026-05-13 13:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260513_1300_0013"
down_revision = "20260513_1200_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "companies",
        sa.Column(
            "name_i18n",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "integrations",
        sa.Column(
            "name_i18n",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )

    op.execute("""
        UPDATE companies
        SET name_i18n = jsonb_build_object('en', name)
        WHERE name IS NOT NULL;
    """)
    op.execute("""
        UPDATE integrations
        SET name_i18n = jsonb_build_object('en', name)
        WHERE name IS NOT NULL;
    """)


def downgrade():
    op.drop_column("integrations", "name_i18n")
    op.drop_column("companies", "name_i18n")