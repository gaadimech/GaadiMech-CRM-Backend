"""add_teleobi_template_id

Revision ID: 90b071546868
Revises: 7bdafc9759e9
Create Date: 2025-12-15 16:03:56.907126

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '90b071546868'
down_revision = '7bdafc9759e9'
branch_labels = None
depends_on = None


def upgrade():
    # Add teleobi_template_id column to teleobi_template_cache table
    op.add_column('teleobi_template_cache', sa.Column('teleobi_template_id', sa.String(length=50), nullable=True))


def downgrade():
    # Remove teleobi_template_id column
    op.drop_column('teleobi_template_cache', 'teleobi_template_id')
