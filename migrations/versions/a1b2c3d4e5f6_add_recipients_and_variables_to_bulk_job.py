"""add_recipients_and_variables_to_bulk_job

Revision ID: a1b2c3d4e5f6
Revises: 9eac0271d6e2
Create Date: 2025-12-16 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9eac0271d6e2'
branch_labels = None
depends_on = None


def upgrade():
    # Add recipients column to store list of recipients for job recovery
    op.add_column('whatsapp_bulk_job', sa.Column('recipients', postgresql.JSON(astext_type=sa.Text()), nullable=True))

    # Add variables column to store template variables for job recovery
    op.add_column('whatsapp_bulk_job', sa.Column('variables', postgresql.JSON(astext_type=sa.Text()), nullable=True))

    # Add template_type column to store template type
    op.add_column('whatsapp_bulk_job', sa.Column('template_type', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('whatsapp_bulk_job', 'template_type')
    op.drop_column('whatsapp_bulk_job', 'variables')
    op.drop_column('whatsapp_bulk_job', 'recipients')


