"""
Database models for the CRM application.
All SQLAlchemy models are defined here.
"""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from pytz import timezone
import pytz
from config import db

# Timezone
ist = timezone('Asia/Kolkata')


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    leads = db.relationship('Lead', backref='creator', lazy=True)

    def set_password(self, password):
        """Hash password before storing"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against hash"""
        return check_password_hash(self.password_hash, password)


class DailyFollowupCount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    initial_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))

    __table_args__ = (db.UniqueConstraint('date', 'user_id', name='unique_daily_count'),)


class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), nullable=False)
    car_registration = db.Column(db.String(20), nullable=True)
    car_model = db.Column(db.String(100), nullable=True)
    followup_date = db.Column(db.DateTime, nullable=False)
    remarks = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='Needs Followup')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    modified_at = db.Column(db.DateTime, default=lambda: datetime.now(ist), onupdate=lambda: datetime.now(ist))
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    __table_args__ = (
        db.CheckConstraint(
            status.in_(['New Lead', 'Did Not Pick Up', 'Needs Followup', 'Confirmed', 'Open', 'Completed', 'Feedback', 'Dead Lead']),
            name='valid_status'
        ),
    )


class UnassignedLead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mobile = db.Column(db.String(15), nullable=False)
    customer_name = db.Column(db.String(100), nullable=True)
    car_manufacturer = db.Column(db.String(50), nullable=True)
    car_model = db.Column(db.String(50), nullable=True)
    pickup_type = db.Column(db.String(20), nullable=True)
    service_type = db.Column(db.String(50), nullable=True)
    scheduled_date = db.Column(db.DateTime, nullable=True)
    source = db.Column(db.String(30), nullable=True)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    assignments = db.relationship('TeamAssignment', backref='unassigned_lead', lazy=True)

    __table_args__ = (
        db.CheckConstraint(
            pickup_type.in_(['Pickup', 'Self Walkin']),
            name='valid_pickup_type'
        ),
        db.CheckConstraint(
            service_type.in_(['Express Car Service', 'Dent Paint', 'AC Service', 'Car Wash', 'Repairs']),
            name='valid_service_type'
        ),
        db.CheckConstraint(
            source.in_(['WhatsApp', 'Chatbot', 'Website', 'Social Media']),
            name='valid_source'
        ),
    )


class TeamAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unassigned_lead_id = db.Column(db.Integer, db.ForeignKey('unassigned_lead.id'), nullable=False)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_date = db.Column(db.Date, nullable=False)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    assigned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Assigned')
    processed_at = db.Column(db.DateTime, nullable=True)
    added_to_crm = db.Column(db.Boolean, default=False)

    assigned_to = db.relationship('User', foreign_keys=[assigned_to_user_id], backref='assigned_leads')
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])

    __table_args__ = (
        db.CheckConstraint(
            status.in_(['Assigned', 'Contacted', 'Added to CRM', 'Ignored']),
            name='valid_assignment_status'
        ),
    )


class PushSubscription(db.Model):
    """Store push notification subscriptions for users"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column('p256dh_key', db.Text, nullable=False)
    auth = db.Column('auth_key', db.Text, nullable=False)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))

    user = db.relationship('User', backref='push_subscriptions')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'endpoint', name='unique_user_endpoint'),
    )


class WorkedLead(db.Model):
    """Tracks when a lead has been worked upon by recording followup date changes."""
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    work_date = db.Column(db.Date, nullable=False)
    old_followup_date = db.Column(db.DateTime, nullable=True)
    new_followup_date = db.Column(db.DateTime, nullable=False)
    worked_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))

    lead = db.relationship('Lead', backref='worked_entries')
    user = db.relationship('User', backref='worked_leads')

    __table_args__ = (
        db.Index('idx_worked_lead_user_date', 'user_id', 'work_date'),
    )


class Template(db.Model):
    """Pre-defined message templates for quick remarks entry."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=True)
    is_global = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usage_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))

    creator = db.relationship('User', backref='templates')


class LeadScore(db.Model):
    """Stores calculated lead scores for prioritization in calling queue."""
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False, unique=True)
    score = db.Column(db.Integer, default=0)
    priority = db.Column(db.String(20), default='Medium')
    overdue_score = db.Column(db.Integer, default=0)
    status_score = db.Column(db.Integer, default=0)
    engagement_score = db.Column(db.Integer, default=0)
    recency_score = db.Column(db.Integer, default=0)
    last_calculated = db.Column(db.DateTime, default=lambda: datetime.now(ist))

    lead = db.relationship('Lead', backref='lead_score', uselist=False)

    __table_args__ = (
        db.Index('idx_lead_score_priority', 'priority', 'score'),
    )


class CallLog(db.Model):
    """Tracks all call activities for analytics and audit trail."""
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    call_sid = db.Column(db.String(100), unique=True, nullable=True)
    from_number = db.Column(db.String(20))
    to_number = db.Column(db.String(20))
    customer_number = db.Column(db.String(20))
    direction = db.Column(db.String(20), nullable=False, default='outbound')
    status = db.Column(db.String(30), nullable=False, default='initiated')
    duration = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    recording_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    call_type = db.Column(db.String(20))
    call_status = db.Column(db.String(30))
    call_started_at = db.Column(db.DateTime)
    call_ended_at = db.Column(db.DateTime)

    lead = db.relationship('Lead', backref='call_logs')
    user = db.relationship('User', backref='call_logs')

    __table_args__ = (
        db.Index('idx_call_log_user_date', 'user_id', 'created_at'),
        db.Index('idx_call_log_lead', 'lead_id'),
        db.Index('idx_call_log_status', 'status'),
        db.Index('idx_call_log_sid', 'call_sid'),
    )


class WhatsAppTemplate(db.Model):
    """Pre-defined WhatsApp message templates for quick customer communication."""
    __tablename__ = 'whatsapp_template'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(ist), onupdate=lambda: datetime.now(ist))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    creator = db.relationship('User', backref='whatsapp_templates')


class CustomerNameCounter(db.Model):
    """Global counter for generating default customer names."""
    __tablename__ = 'customer_name_counter'

    id = db.Column(db.Integer, primary_key=True)
    counter = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(ist), onupdate=lambda: datetime.now(ist))


class TeleobiTemplateCache(db.Model):
    """Cache for Teleobi WhatsApp templates to avoid frequent API calls."""
    __tablename__ = 'teleobi_template_cache'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.String(100), nullable=False, unique=True)
    teleobi_template_id = db.Column(db.String(50), nullable=True)
    template_name = db.Column(db.String(200), nullable=False)
    template_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    language = db.Column(db.String(10), default='en_US')
    variables = db.Column(db.JSON, nullable=True)
    template_json = db.Column(db.Text, nullable=True)
    whatsapp_business_id = db.Column(db.Integer, nullable=True)
    phone_number_id = db.Column(db.String(100), nullable=False)
    synced_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))

    __table_args__ = (
        db.Index('idx_template_type', 'template_type'),
        db.Index('idx_template_status', 'status'),
        db.Index('idx_template_synced', 'synced_at'),
    )


class WhatsAppSend(db.Model):
    """Track all WhatsApp template messages sent via Teleobi API."""
    __tablename__ = 'whatsapp_send'

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=True)
    phone_number = db.Column(db.String(20), nullable=False)
    template_id = db.Column(db.String(100), nullable=True)
    template_name = db.Column(db.String(200), nullable=False)
    template_type = db.Column(db.String(20), nullable=True)
    variables = db.Column(db.JSON, nullable=True)
    wa_message_id = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), nullable=False, default='pending')
    sent_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(ist), onupdate=lambda: datetime.now(ist))

    lead = db.relationship('Lead', backref='whatsapp_sends')
    creator = db.relationship('User', backref='whatsapp_sends')

    __table_args__ = (
        db.Index('idx_whatsapp_send_status', 'status'),
        db.Index('idx_whatsapp_send_phone', 'phone_number'),
        db.Index('idx_whatsapp_send_template', 'template_name'),
        db.Index('idx_whatsapp_send_created', 'created_at'),
        db.Index('idx_whatsapp_send_wa_id', 'wa_message_id'),
    )


class WhatsAppBulkJob(db.Model):
    """Track bulk messaging jobs for monitoring and management."""
    __tablename__ = 'whatsapp_bulk_job'

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(200), nullable=True)
    template_name = db.Column(db.String(200), nullable=False)
    template_type = db.Column(db.String(20), nullable=True)
    total_recipients = db.Column(db.Integer, nullable=False, default=0)
    processed_count = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    delivered_count = db.Column(db.Integer, default=0)
    read_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), nullable=False, default='pending')
    filter_criteria = db.Column(db.JSON, nullable=True)
    recipients = db.Column(db.JSON, nullable=True)
    variables = db.Column(db.JSON, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(ist), onupdate=lambda: datetime.now(ist))

    creator = db.relationship('User', backref='whatsapp_bulk_jobs')

    __table_args__ = (
        db.Index('idx_bulk_job_status', 'status'),
        db.Index('idx_bulk_job_created', 'created_at'),
    )

