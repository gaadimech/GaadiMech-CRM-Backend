"""merge_heads

Revision ID: 7bdafc9759e9
Revises: add_car_model_lead, add_push_subscriptions, add_whatsapp_bulk_messaging, add_worked_lead_tracking
Create Date: 2025-12-15 15:16:05.609063

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7bdafc9759e9'
down_revision = ('add_car_model_lead', 'add_push_subscriptions', 'add_whatsapp_bulk_messaging', 'add_worked_lead_tracking')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
