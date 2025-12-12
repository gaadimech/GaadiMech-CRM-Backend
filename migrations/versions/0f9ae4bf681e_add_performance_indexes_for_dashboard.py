"""add_performance_indexes_for_dashboard

Revision ID: 0f9ae4bf681e
Revises: add_missing_indexes
Create Date: 2025-05-31 10:45:45.789123

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0f9ae4bf681e'
down_revision = 'add_missing_indexes'
branch_labels = None
depends_on = None


def upgrade():
    # Add additional performance indexes
    with op.batch_alter_table('lead', schema=None) as batch_op:
        # Index for mobile number searches (used in followups page)
        batch_op.create_index('idx_lead_mobile', ['mobile'], unique=False)
        
        # Index for car registration searches
        batch_op.create_index('idx_lead_car_reg', ['car_registration'], unique=False)
        
        # Compound index for status and created_at (for reporting)
        batch_op.create_index('idx_lead_status_created', ['status', 'created_at'], unique=False)
        
        # Compound index for status and followup_date (for dashboard filtering)
        batch_op.create_index('idx_lead_status_followup', ['status', 'followup_date'], unique=False)


def downgrade():
    # Remove the additional indexes
    with op.batch_alter_table('lead', schema=None) as batch_op:
        batch_op.drop_index('idx_lead_mobile')
        batch_op.drop_index('idx_lead_car_reg')
        batch_op.drop_index('idx_lead_status_created')
        batch_op.drop_index('idx_lead_status_followup')
