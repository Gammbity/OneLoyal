"""add i18n columns for campaigns and gift_tiers

Revision ID: 20260513_1200_0012
Revises: 0012
Create Date: 2026-05-13 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260513_1200_0012'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    # campaigns
    op.add_column(
        'campaigns',
        sa.Column('title_i18n', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
    )
    op.add_column(
        'campaigns',
        sa.Column('description_i18n', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # gift_tiers
    op.add_column(
        'gift_tiers',
        sa.Column('title_i18n', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
    )
    op.add_column(
        'gift_tiers',
        sa.Column('description_i18n', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # populate defaults from existing title/description
    op.execute("""
        UPDATE campaigns
        SET title_i18n = jsonb_build_object('en', title)
        WHERE title IS NOT NULL;
    """)
    op.execute("""
        UPDATE campaigns
        SET description_i18n = jsonb_build_object('en', description)
        WHERE description IS NOT NULL;
    """)
    op.execute("""
        UPDATE gift_tiers
        SET title_i18n = jsonb_build_object('en', title)
        WHERE title IS NOT NULL;
    """)
    op.execute("""
        UPDATE gift_tiers
        SET description_i18n = jsonb_build_object('en', description)
        WHERE description IS NOT NULL;
    """)


def downgrade():
    op.drop_column('gift_tiers', 'description_i18n')
    op.drop_column('gift_tiers', 'title_i18n')
    op.drop_column('campaigns', 'description_i18n')
    op.drop_column('campaigns', 'title_i18n')
