"""Add missing indexes for performance optimization

Revision ID: add_missing_indexes
Revises: 66a48b827fa7
Create Date: 2025-02-07 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_missing_indexes'
down_revision = '66a48b827fa7'
branch_labels = None
depends_on = None


def upgrade():
    # Add critical indexes for dashboard performance
    with op.batch_alter_table('lead', schema=None) as batch_op:
        # Index for creator_id - critical for user filtering
        batch_op.create_index('idx_lead_creator_id', ['creator_id'], unique=False)
        
        # Index for followup_date - critical for date-based dashboard queries
        batch_op.create_index('idx_lead_followup_date', ['followup_date'], unique=False)
        
        # Index for status - used in quick stats and filtering
        batch_op.create_index('idx_lead_status', ['status'], unique=False)
        
        # Compound index for the most common dashboard query pattern
        batch_op.create_index('idx_lead_creator_followup', ['creator_id', 'followup_date'], unique=False)
        
        # Index for created_at - used for daily performance metrics
        batch_op.create_index('idx_lead_created_at', ['created_at'], unique=False)
        
        # Compound index for performance calculations
        batch_op.create_index('idx_lead_creator_created', ['creator_id', 'created_at'], unique=False)

    # Add index for daily followup count table
    with op.batch_alter_table('daily_followup_count', schema=None) as batch_op:
        # Index for quick lookups by user and date
        batch_op.create_index('idx_daily_followup_user_date', ['user_id', 'date'], unique=False)


def downgrade():
    # Remove the indexes
    with op.batch_alter_table('lead', schema=None) as batch_op:
        batch_op.drop_index('idx_lead_creator_id')
        batch_op.drop_index('idx_lead_followup_date')
        batch_op.drop_index('idx_lead_status')
        batch_op.drop_index('idx_lead_creator_followup')
        batch_op.drop_index('idx_lead_created_at')
        batch_op.drop_index('idx_lead_creator_created')
    
    with op.batch_alter_table('daily_followup_count', schema=None) as batch_op:
        batch_op.drop_index('idx_daily_followup_user_date') 