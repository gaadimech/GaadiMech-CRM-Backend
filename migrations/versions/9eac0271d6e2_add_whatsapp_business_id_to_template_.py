"""add_whatsapp_business_id_to_template_cache

Revision ID: 9eac0271d6e2
Revises: 0938d34e5593
Create Date: 2025-12-16 00:37:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9eac0271d6e2'
down_revision = '0938d34e5593'
branch_labels = None
depends_on = None


def upgrade():
    # Add whatsapp_business_id column to store per-template bot ID
    op.add_column('teleobi_template_cache', sa.Column('whatsapp_business_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('teleobi_template_cache', 'whatsapp_business_id')
