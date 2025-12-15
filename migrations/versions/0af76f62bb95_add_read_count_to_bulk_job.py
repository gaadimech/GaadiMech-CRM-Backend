"""add_read_count_to_bulk_job

Revision ID: 0af76f62bb95
Revises: 90b071546868
Create Date: 2025-12-15 17:17:32.639923

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0af76f62bb95'
down_revision = '90b071546868'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('whatsapp_bulk_job', sa.Column('read_count', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    op.drop_column('whatsapp_bulk_job', 'read_count')
