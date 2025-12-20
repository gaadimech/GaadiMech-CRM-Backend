"""add fcm support to push subscription

Revision ID: add_fcm_support
Revises: 
Create Date: 2024-12-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_fcm_support'
down_revision = 'add_push_subscriptions'  # Update this to the latest migration revision
branch_labels = None
depends_on = None


def upgrade():
    # Add FCM token column
    op.add_column('push_subscription', sa.Column('fcm_token', sa.Text(), nullable=True))
    
    # Add subscription_type column with default 'vapid'
    op.add_column('push_subscription', sa.Column('subscription_type', sa.String(length=20), nullable=True, server_default='vapid'))
    
    # Add updated_at column
    op.add_column('push_subscription', sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # Make endpoint, p256dh, and auth nullable (for FCM-only subscriptions)
    op.alter_column('push_subscription', 'endpoint', nullable=True)
    op.alter_column('push_subscription', 'p256dh_key', nullable=True)
    op.alter_column('push_subscription', 'auth_key', nullable=True)
    
    # Add unique constraint for FCM token
    op.create_unique_constraint('unique_user_fcm_token', 'push_subscription', ['user_id', 'fcm_token'])
    
    # Update existing subscriptions to have type 'vapid'
    op.execute("UPDATE push_subscription SET subscription_type = 'vapid' WHERE subscription_type IS NULL")


def downgrade():
    # Remove unique constraint
    op.drop_constraint('unique_user_fcm_token', 'push_subscription', type_='unique')
    
    # Remove columns
    op.drop_column('push_subscription', 'updated_at')
    op.drop_column('push_subscription', 'subscription_type')
    op.drop_column('push_subscription', 'fcm_token')
    
    # Make columns non-nullable again (if needed)
    op.alter_column('push_subscription', 'auth_key', nullable=False)
    op.alter_column('push_subscription', 'p256dh_key', nullable=False)
    op.alter_column('push_subscription', 'endpoint', nullable=False)

