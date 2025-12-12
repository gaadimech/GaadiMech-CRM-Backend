"""Add security fixes and new feature tables

Revision ID: 001_security_features
Revises: 
Create Date: 2025-11-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from werkzeug.security import generate_password_hash

# revision identifiers, used by Alembic.
revision = '001_security_features'
down_revision = None
depends_on = None


def upgrade():
    # 1. Alter User table - add mobile and increase password_hash length
    op.add_column('user', sa.Column('mobile', sa.String(length=15), nullable=True))
    
    # Note: Changing column length requires more complex migration
    # For PostgreSQL, we can use:
    op.execute("ALTER TABLE \"user\" ALTER COLUMN password_hash TYPE VARCHAR(255)")
    
    # 2. Re-hash existing passwords (CRITICAL SECURITY FIX)
    # This will re-hash the plain text passwords that are currently stored
    connection = op.get_bind()
    users = connection.execute(sa.text("SELECT id, password_hash FROM \"user\"")).fetchall()
    
    for user in users:
        user_id, plain_password = user
        hashed_password = generate_password_hash(plain_password)
        connection.execute(
            sa.text("UPDATE \"user\" SET password_hash = :hash WHERE id = :id"),
            {"hash": hashed_password, "id": user_id}
        )
    
    # 3. Create Template table
    op.create_table('template',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('is_global', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 4. Create LeadScore table
    op.create_table('lead_score',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=True),
        sa.Column('overdue_score', sa.Integer(), nullable=True),
        sa.Column('status_score', sa.Integer(), nullable=True),
        sa.Column('engagement_score', sa.Integer(), nullable=True),
        sa.Column('recency_score', sa.Integer(), nullable=True),
        sa.Column('last_calculated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lead_id')
    )
    op.create_index('idx_lead_score_priority', 'lead_score', ['priority', 'score'], unique=False)
    
    # 5. Create CallLog table
    op.create_table('call_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('call_type', sa.String(length=20), nullable=False),
        sa.Column('call_status', sa.String(length=30), nullable=False),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('recording_url', sa.String(length=500), nullable=True),
        sa.Column('call_started_at', sa.DateTime(), nullable=True),
        sa.Column('call_ended_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_call_log_user_date', 'call_log', ['user_id', 'call_started_at'], unique=False)
    
    # 6. Add performance indexes to existing tables
    op.create_index('idx_lead_creator_followup', 'lead', ['creator_id', 'followup_date'], unique=False)
    op.create_index('idx_lead_status', 'lead', ['status'], unique=False)
    op.create_index('idx_lead_mobile', 'lead', ['mobile'], unique=False)
    op.create_index('idx_lead_created_at', 'lead', ['created_at'], unique=False)
    op.create_index('idx_lead_modified_at', 'lead', ['modified_at'], unique=False)
    
    op.create_index('idx_daily_followup_user_date', 'daily_followup_count', ['user_id', 'date'], unique=False)
    op.create_index('idx_worked_lead_user_date', 'worked_lead', ['user_id', 'work_date'], unique=False)
    
    op.create_index('idx_unassigned_mobile', 'unassigned_lead', ['mobile'], unique=False)
    op.create_index('idx_unassigned_created', 'unassigned_lead', ['created_at'], unique=False)
    
    op.create_index('idx_assignment_user_date', 'team_assignment', ['assigned_to_user_id', 'assigned_date'], unique=False)
    op.create_index('idx_assignment_status', 'team_assignment', ['status'], unique=False)
    
    # 7. Insert default templates
    connection = op.get_bind()
    admin_user = connection.execute(sa.text("SELECT id FROM \"user\" WHERE is_admin = true LIMIT 1")).fetchone()
    
    if admin_user:
        admin_id = admin_user[0]
        default_templates = [
            ("Customer Interested", "Customer is interested in the service. Will follow up on [date].", "Interested"),
            ("Not Interested", "Customer is not interested at this time. Will try again after 30 days.", "Not Interested"),
            ("Call Back Later", "Customer requested a callback. Best time to call: [time].", "Callback"),
            ("Wrong Number", "Wrong number or phone switched off.", "General"),
            ("Already Serviced", "Customer has already serviced their vehicle elsewhere.", "Not Interested"),
            ("Price Issue", "Customer finds pricing too high. Offered discount of [amount].", "Negotiation"),
            ("Appointment Scheduled", "Appointment scheduled for [date] at [time]. Service type: [service].", "Confirmed"),
            ("Vehicle Details Needed", "Need more details about vehicle: Make, Model, Year.", "Information Required"),
            ("Payment Discussed", "Discussed payment options. Customer prefers [payment_method].", "Negotiation"),
            ("Competitor Mentioned", "Customer comparing with [competitor_name].", "Competition"),
        ]
        
        for title, content, category in default_templates:
            connection.execute(
                sa.text("INSERT INTO template (title, content, category, is_global, created_by, usage_count, created_at) VALUES (:title, :content, :category, true, :created_by, 0, NOW())"),
                {"title": title, "content": content, "category": category, "created_by": admin_id}
            )


def downgrade():
    # Remove indexes
    op.drop_index('idx_assignment_status', table_name='team_assignment')
    op.drop_index('idx_assignment_user_date', table_name='team_assignment')
    op.drop_index('idx_unassigned_created', table_name='unassigned_lead')
    op.drop_index('idx_unassigned_mobile', table_name='unassigned_lead')
    op.drop_index('idx_worked_lead_user_date', table_name='worked_lead')
    op.drop_index('idx_daily_followup_user_date', table_name='daily_followup_count')
    op.drop_index('idx_lead_modified_at', table_name='lead')
    op.drop_index('idx_lead_created_at', table_name='lead')
    op.drop_index('idx_lead_mobile', table_name='lead')
    op.drop_index('idx_lead_status', table_name='lead')
    op.drop_index('idx_lead_creator_followup', table_name='lead')
    
    # Remove new tables
    op.drop_index('idx_call_log_user_date', table_name='call_log')
    op.drop_table('call_log')
    op.drop_index('idx_lead_score_priority', table_name='lead_score')
    op.drop_table('lead_score')
    op.drop_table('template')
    
    # Revert user table changes (passwords will be lost - this is one-way)
    op.drop_column('user', 'mobile')
