"""Add WhatsAppTemplate table for message templates

Revision ID: add_whatsapp_templates
Revises: 001_security_features
Create Date: 2025-12-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_whatsapp_templates'
down_revision = '001_security_features'
branch_labels = None
depends_on = None


def upgrade():
    # Create WhatsAppTemplate table
    op.create_table('whatsapp_template',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for better performance
    with op.batch_alter_table('whatsapp_template', schema=None) as batch_op:
        batch_op.create_index('idx_whatsapp_template_created_by', ['created_by'], unique=False)
        batch_op.create_index('idx_whatsapp_template_created_at', ['created_at'], unique=False)


def downgrade():
    # Drop the table
    op.drop_table('whatsapp_template')

