"""Add car_model column to Lead table

Revision ID: add_car_model_lead
Revises: 66a48b827fa7
Create Date: 2025-12-10 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_car_model_lead'
down_revision = '66a48b827fa7'
branch_labels = None
depends_on = None


def upgrade():
    # Add car_model column to lead table
    with op.batch_alter_table('lead', schema=None) as batch_op:
        batch_op.add_column(sa.Column('car_model', sa.String(length=100), nullable=True))


def downgrade():
    # Remove car_model column from lead table
    with op.batch_alter_table('lead', schema=None) as batch_op:
        batch_op.drop_column('car_model')

