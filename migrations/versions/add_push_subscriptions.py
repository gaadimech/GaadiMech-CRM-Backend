"""add push subscriptions

Revision ID: add_push_subscriptions
Revises: add_worked_lead_tracking
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_push_subscriptions'
down_revision = None  # Multiple heads - will be merged
branch_labels = None
depends_on = ('add_car_model_lead', 'add_whatsapp_templates', 'add_worked_lead_tracking')


def upgrade():
    # Create push_subscription table
    op.create_table(
        'push_subscription',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('p256dh', sa.Text(), nullable=False),
        sa.Column('auth', sa.Text(), nullable=False),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'endpoint', name='unique_user_endpoint')
    )
    op.create_index(op.f('ix_push_subscription_user_id'), 'push_subscription', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_push_subscription_user_id'), table_name='push_subscription')
    op.drop_table('push_subscription')

