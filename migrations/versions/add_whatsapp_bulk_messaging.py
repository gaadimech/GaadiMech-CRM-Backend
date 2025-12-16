"""Add WhatsApp bulk messaging tables

Revision ID: add_whatsapp_bulk_messaging
Revises:
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_whatsapp_bulk_messaging'
down_revision = 'add_whatsapp_templates'  # Update this with the latest revision
branch_labels = None
depends_on = None


def upgrade():
    # Create teleobi_template_cache table
    op.create_table(
        'teleobi_template_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.String(length=100), nullable=False),
        sa.Column('template_name', sa.String(length=200), nullable=False),
        sa.Column('template_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('variables', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('template_json', sa.Text(), nullable=True),
        sa.Column('phone_number_id', sa.String(length=100), nullable=False),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id')
    )
    op.create_index('idx_template_type', 'teleobi_template_cache', ['template_type'])
    op.create_index('idx_template_status', 'teleobi_template_cache', ['status'])
    op.create_index('idx_template_synced', 'teleobi_template_cache', ['synced_at'])

    # Create whatsapp_send table
    op.create_table(
        'whatsapp_send',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('template_id', sa.String(length=100), nullable=True),
        sa.Column('template_name', sa.String(length=200), nullable=False),
        sa.Column('template_type', sa.String(length=20), nullable=True),
        sa.Column('variables', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('wa_message_id', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_whatsapp_send_status', 'whatsapp_send', ['status'])
    op.create_index('idx_whatsapp_send_phone', 'whatsapp_send', ['phone_number'])
    op.create_index('idx_whatsapp_send_template', 'whatsapp_send', ['template_name'])
    op.create_index('idx_whatsapp_send_created', 'whatsapp_send', ['created_at'])
    op.create_index('idx_whatsapp_send_wa_id', 'whatsapp_send', ['wa_message_id'])

    # Create whatsapp_bulk_job table
    op.create_table(
        'whatsapp_bulk_job',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_name', sa.String(length=200), nullable=True),
        sa.Column('template_name', sa.String(length=200), nullable=False),
        sa.Column('total_recipients', sa.Integer(), nullable=False),
        sa.Column('sent_count', sa.Integer(), nullable=True),
        sa.Column('delivered_count', sa.Integer(), nullable=True),
        sa.Column('failed_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('filter_criteria', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_bulk_job_status', 'whatsapp_bulk_job', ['status'])
    op.create_index('idx_bulk_job_created', 'whatsapp_bulk_job', ['created_at'])


def downgrade():
    op.drop_index('idx_bulk_job_created', table_name='whatsapp_bulk_job')
    op.drop_index('idx_bulk_job_status', table_name='whatsapp_bulk_job')
    op.drop_table('whatsapp_bulk_job')

    op.drop_index('idx_whatsapp_send_wa_id', table_name='whatsapp_send')
    op.drop_index('idx_whatsapp_send_created', table_name='whatsapp_send')
    op.drop_index('idx_whatsapp_send_template', table_name='whatsapp_send')
    op.drop_index('idx_whatsapp_send_phone', table_name='whatsapp_send')
    op.drop_index('idx_whatsapp_send_status', table_name='whatsapp_send')
    op.drop_table('whatsapp_send')

    op.drop_index('idx_template_synced', table_name='teleobi_template_cache')
    op.drop_index('idx_template_status', table_name='teleobi_template_cache')
    op.drop_index('idx_template_type', table_name='teleobi_template_cache')
    op.drop_table('teleobi_template_cache')

