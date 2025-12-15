from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from datetime import datetime, timedelta, time
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import quote_plus
import re
import os
import sys
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address   
from flask_migrate import Migrate
from pytz import timezone
import pytz
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import json
from pywebpush import webpush, WebPushException

# Load environment variables
load_dotenv()

# Try to import text_parser with fallback
try:
    from text_parser import parse_customer_text
except ImportError:
    def parse_customer_text(text):
        return {"error": "Text parser not available"}

application = Flask(__name__)
application.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'GaadiMech2024!')

# Configure CORS for frontend API requests
# In production, frontend and backend are on the same domain, so CORS should not be needed
# However, we configure it to handle any edge cases
IS_PRODUCTION = os.getenv('FLASK_ENV') == 'production' or os.getenv('EB_ENVIRONMENT') is not None

# Use a simple CORS configuration
# For same-origin requests, CORS headers are ignored by the browser
# For cross-origin, we allow all origins but without credentials (cookies work via same-origin anyway)
if IS_PRODUCTION:
    # For production: Use exact Elastic Beanstalk origin with credentials support
    # The frontend uses credentials: "include" for session cookies
    # Get the origin from environment or use the known EB URL
    EB_ORIGIN_STR = os.getenv('EB_ORIGIN', 'http://gaadimech-crm-unified.eba-ftgmu9fp.ap-south-1.elasticbeanstalk.com')
    # Parse comma-separated origins (e.g., "https://crm.gaadimech.com,http://crm.gaadimech.com")
    EB_ORIGINS = [origin.strip() for origin in EB_ORIGIN_STR.split(',') if origin.strip()]
    print(f"CORS configured for origins: {EB_ORIGINS}")
    CORS(application,
         origins=EB_ORIGINS,  # List of allowed origins
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
         allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With", "Origin"],
         supports_credentials=True,  # Required for credentials: "include" in frontend
         max_age=3600,
         automatic_options=True)
else:
    # In development, allow localhost origins with credentials
    CORS(application, 
         origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
         allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With", "Origin"],
         supports_credentials=True,
         max_age=3600,
         automatic_options=True)

# Database configuration with better error handling
# IMPORTANT: Always use RDS_HOST from environment, not from DATABASE_URL
# This ensures we use the correct database hostname
RDS_HOST = os.getenv("RDS_HOST", "crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com")
RDS_DB = os.getenv("RDS_DB", "crmportal")
RDS_USER = os.getenv("RDS_USER", "crmadmin")
RDS_PASSWORD = os.getenv("RDS_PASSWORD", "GaadiMech2024!")
RDS_PORT = os.getenv("RDS_PORT", "5432")

# URL-encode the password to handle special characters like ! @ # etc.
# The "!" in "GaadiMech2024!" needs to be encoded as "%21" in the connection URL
RDS_PASSWORD_ENCODED = quote_plus(RDS_PASSWORD)

# Build DATABASE_URL from individual components to ensure correct hostname
# Use URL-encoded password to prevent special character issues
DATABASE_URL = f"postgresql+psycopg2://{RDS_USER}:{RDS_PASSWORD_ENCODED}@{RDS_HOST}:{RDS_PORT}/{RDS_DB}"

# Debug: Print actual password being used (without exposing full password)
print(f"RDS Password (first 5 chars): {RDS_PASSWORD[:5]}...")
print(f"RDS Password Encoded: {RDS_PASSWORD_ENCODED[:10]}...")

# Validate that we're using the correct database hostname
if "gaadimech-crm-db" in DATABASE_URL:
    print(f"ERROR: Wrong database hostname detected! Fixing...")
    # Replace wrong hostname with correct one
    DATABASE_URL = DATABASE_URL.replace("gaadimech-crm-db", "crm-portal-db")
    print(f"Fixed DATABASE_URL to use correct hostname")

# Handle postgres:// to postgresql+psycopg2:// conversion
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

print(f"Database URL configured: {DATABASE_URL[:80]}...")
print(f"Database Host: {RDS_HOST}")

application.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# AWS optimized database settings
# RDS requires SSL encryption - use 'require' instead of 'prefer'
application.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'pool_recycle': 1800,
    'pool_pre_ping': True,
    'connect_args': {
        'connect_timeout': 30,
        'sslmode': 'require'  # Changed from 'prefer' to 'require' - RDS requires SSL
    }
}

# Session configuration
# Detect if running in production with HTTPS
IS_PRODUCTION = os.getenv('FLASK_ENV') == 'production'
FORCE_HTTPS = os.getenv('FORCE_HTTPS', 'false').lower() == 'true'

# Check if we're behind a proxy that terminates HTTPS (Elastic Beanstalk ALB)
# If X-Forwarded-Proto is https, then cookies should be secure
# Otherwise, if we're on HTTP, cookies should NOT be secure
USE_SECURE_COOKIES = FORCE_HTTPS or (IS_PRODUCTION and os.getenv('USE_SECURE_COOKIES', 'false').lower() == 'true')

# For HTTP deployments (like Elastic Beanstalk without HTTPS), we need insecure cookies
# Secure cookies only work over HTTPS, and will be rejected by browsers on HTTP
# This is the KEY DIFFERENCE between local (HTTP, insecure cookies work) and AWS (HTTP, secure cookies fail)
application.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to False for HTTP - this is why it works locally but not on AWS!
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_DOMAIN=None,  # None means cookie is set for current domain (works for EB subdomains)
    REMEMBER_COOKIE_SECURE=False,  # Set to False for HTTP
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_DURATION=timedelta(hours=24),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24)
)

# Initialize extensions
db = SQLAlchemy(application)
migrate = Migrate(application, db)
login_manager = LoginManager()
login_manager.init_app(application)
login_manager.login_view = 'login'
login_manager.session_protection = "basic"
login_manager.refresh_view = "login"
login_manager.needs_refresh_message = "Please login again to confirm your identity"
login_manager.needs_refresh_message_category = "info"

# Test database connection on startup (works with gunicorn)
def test_database_connection():
    """Test database connection on application startup"""
    try:
        with application.app_context():
            # Simple query to test connection
            db.session.execute(text("SELECT 1"))
            db.session.commit()
            print("✅ Database connection test successful")
            return True
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test connection when module is imported (runs with gunicorn)
test_database_connection()

# Simple cache
dashboard_cache_store = {}

# Configure rate limiter with fallback
try:
    limiter = Limiter(
        key_func=get_remote_address,
        app=application,
        storage_uri="memory://"
    )
except Exception as e:
    print(f"Rate limiter initialization failed: {e}")
    # Create a dummy limiter for deployment
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator
    limiter = DummyLimiter()

# Timezone
ist = timezone('Asia/Kolkata')

def normalize_mobile_number(mobile):
    """
    Normalize mobile number to accept three formats:
    1. +91XXXXXXXXXX (13 characters: +91 + 10 digits)
    2. XXXXXXXXXX (10 digits)
    3. 91XXXXXXXXXX (12 digits: 91 + 10 digits)
    
    Returns normalized mobile number (10 digits) or None if invalid.
    Accepts any 10-digit number to support old leads that may not follow
    the standard Indian mobile number format (starting with 6-9).
    """
    if not mobile:
        return None
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', str(mobile))
    
    # Handle +91 format
    if cleaned.startswith('+91'):
        digits = cleaned[3:]  # Remove +91
        if len(digits) == 10:
            return digits
    # Handle 91XXXXXXXXXX format
    elif cleaned.startswith('91'):
        digits = cleaned[2:]  # Remove 91
        if len(digits) == 10:
            return digits
    # Handle XXXXXXXXXX format (10 digits)
    elif len(cleaned) == 10:
        return cleaned
    
    return None

# Mobile mapping
USER_MOBILE_MAPPING = {
    'Hemlata': '9672562111',
    'Sneha': '+919672764111'
}

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)  # Increased length for hashed passwords
    name = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    # Note: User mobile numbers are stored in USER_MOBILE_MAPPING, not in database
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
    pickup_type = db.Column(db.String(20), nullable=True)  # 'Pickup' or 'Self Walkin'
    service_type = db.Column(db.String(50), nullable=True)
    scheduled_date = db.Column(db.DateTime, nullable=True)
    source = db.Column(db.String(30), nullable=True)  # 'WhatsApp', 'Chatbot', 'Website', 'Social Media'
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationship to team assignments
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
    
    # Relationships
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
    p256dh = db.Column('p256dh_key', db.Text, nullable=False)  # Public key (mapped to p256dh_key in DB)
    auth = db.Column('auth_key', db.Text, nullable=False)  # Auth secret (mapped to auth_key in DB)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    # Note: updated_at column doesn't exist in current DB structure
    
    # Relationship
    user = db.relationship('User', backref='push_subscriptions')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'endpoint', name='unique_user_endpoint'),
    )

class WorkedLead(db.Model):
    """
    Tracks when a lead has been worked upon by recording followup date changes.
    This is used to calculate completion rates and track user performance.
    """
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    work_date = db.Column(db.Date, nullable=False)  # Date when the work was done
    old_followup_date = db.Column(db.DateTime, nullable=True)  # Previous followup date
    new_followup_date = db.Column(db.DateTime, nullable=False)  # New followup date
    worked_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    
    # Relationships
    lead = db.relationship('Lead', backref='worked_entries')
    user = db.relationship('User', backref='worked_leads')
    
    __table_args__ = (
        db.Index('idx_worked_lead_user_date', 'user_id', 'work_date'),
    )

class Template(db.Model):
    """
    Pre-defined message templates for quick remarks entry.
    Helps telecallers save time by reusing common messages.
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=True)  # e.g., 'Interested', 'Not Interested', 'Callback', 'General'
    is_global = db.Column(db.Boolean, default=True)  # True = available to all, False = personal
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usage_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    
    creator = db.relationship('User', backref='templates')

class LeadScore(db.Model):
    """
    Stores calculated lead scores for prioritization in calling queue.
    Score is calculated based on multiple factors.
    """
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False, unique=True)
    score = db.Column(db.Integer, default=0)  # 0-100
    priority = db.Column(db.String(20), default='Medium')  # High, Medium, Low
    
    # Score factors
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
    """
    Tracks all call activities for analytics and audit trail.
    """
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=True)  # Nullable for non-lead calls
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Call tracking fields
    call_sid = db.Column(db.String(100), unique=True, nullable=True)  # Call SID (for external call services)
    from_number = db.Column(db.String(20))  # Caller ID
    to_number = db.Column(db.String(20))  # User's number
    customer_number = db.Column(db.String(20))  # Customer's number
    
    # Call metadata
    direction = db.Column(db.String(20), nullable=False, default='outbound')  # 'outbound', 'inbound'
    status = db.Column(db.String(30), nullable=False, default='initiated')  # 'initiated', 'ringing', 'answered', 'completed', 'failed', 'busy', 'no-answer'
    duration = db.Column(db.Integer, default=0)  # in seconds
    notes = db.Column(db.Text)
    recording_url = db.Column(db.String(500))  # URL to call recording if available
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    
    # Legacy fields for backwards compatibility
    call_type = db.Column(db.String(20))  # Deprecated - use 'direction' instead
    call_status = db.Column(db.String(30))  # Deprecated - use 'status' instead
    call_started_at = db.Column(db.DateTime)  # Deprecated - use 'created_at' instead
    call_ended_at = db.Column(db.DateTime)  # Deprecated - use 'updated_at' instead
    
    lead = db.relationship('Lead', backref='call_logs')
    user = db.relationship('User', backref='call_logs')
    
    __table_args__ = (
        db.Index('idx_call_log_user_date', 'user_id', 'created_at'),
        db.Index('idx_call_log_lead', 'lead_id'),
        db.Index('idx_call_log_status', 'status'),
        db.Index('idx_call_log_sid', 'call_sid'),
    )

class WhatsAppTemplate(db.Model):
    """
    Pre-defined WhatsApp message templates for quick customer communication.
    Users can select a template when clicking WhatsApp button, and it will be prefilled in the chat.
    """
    __tablename__ = 'whatsapp_template'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Template name/identifier
    message = db.Column(db.Text, nullable=False)  # The actual message content
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(ist), onupdate=lambda: datetime.now(ist))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    creator = db.relationship('User', backref='whatsapp_templates')

class CustomerNameCounter(db.Model):
    """
    Global counter for generating default customer names.
    Stores a single row with the current counter value.
    Ensures unique sequential customer names across all users and sessions.
    """
    __tablename__ = 'customer_name_counter'
    
    id = db.Column(db.Integer, primary_key=True)
    counter = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(ist), onupdate=lambda: datetime.now(ist))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@application.route('/login', methods=['GET', 'POST', 'OPTIONS'])
@limiter.limit("20 per minute", methods=['POST'])  # Only rate limit POST requests, not GET
def login():
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept, X-Requested-With, Origin')
        return response
    
    # For GET requests, always serve Next.js frontend
    if request.method == 'GET':
        return serve_frontend()
    
    # For POST requests, handle as API login
    try:
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            return jsonify({'success': True, 'message': 'Already logged in', 'user': {'id': current_user.id, 'username': current_user.username, 'name': current_user.name, 'is_admin': current_user.is_admin}})
    except Exception:
        pass  # User not authenticated, continue with login

    if request.method == 'POST':
        # Handle both JSON and form-urlencoded requests
        if request.is_json:
            data = request.get_json()
            username = data.get('username', '')
            password = data.get('password', '')
        else:
            username = request.form.get('username', '')
            password = request.form.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required'}), 400
        
        try:
            # Query user from database
            print(f"Attempting to query user: {username}")
            user = User.query.filter_by(username=username).first()
            print(f"User found: {user is not None}")
            
            if not user:
                print(f"User '{username}' not found in database")
                return jsonify({'success': False, 'message': 'Invalid username or password'}), 401
            
            # Check password
            password_valid = user.check_password(password)
            print(f"Password valid: {password_valid}")
            
            if not password_valid:
                print(f"Invalid password for user '{username}'")
                return jsonify({'success': False, 'message': 'Invalid username or password'}), 401
            
            # Login user
            login_user(user, remember=True)
            print(f"User '{username}' logged in successfully")
            
            # Commit session if needed
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'name': user.name,
                    'is_admin': user.is_admin
                }
            })
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Login error: {str(e)}")
            print(f"Traceback: {error_trace}")
            db.session.rollback()
            # Return more detailed error in development, generic in production
            if application.debug:
                error_msg = f'An error occurred during login: {str(e)}'
            else:
                error_msg = 'An error occurred during login. Please try again.'
            return jsonify({'success': False, 'message': error_msg}), 500
    
    # Default: serve Next.js frontend
    return serve_frontend()

@application.after_request
def after_request(response):
    """Add CORS headers to all responses (fallback for development only)"""
    # Flask-CORS should handle CORS in production, but we keep this for development
    if not IS_PRODUCTION:
        origin = request.headers.get('Origin', '')
        # Allow requests from frontend development servers
        allowed_origins = [
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'http://localhost:3001',
            'http://127.0.0.1:3001'
        ]
        
        if origin in allowed_origins or any(origin.startswith(orig) for orig in allowed_origins):
            # Don't override if Flask-CORS already set it
            if 'Access-Control-Allow-Origin' not in response.headers:
                response.headers.add('Access-Control-Allow-Origin', origin)
            if 'Access-Control-Allow-Credentials' not in response.headers:
                response.headers.add('Access-Control-Allow-Credentials', 'true')
            if 'Access-Control-Allow-Methods' not in response.headers:
                response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS, PATCH')
            if 'Access-Control-Allow-Headers' not in response.headers:
                response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept, X-Requested-With, Origin')
    return response

@application.teardown_request
def teardown_request(exception=None):
    """Ensure proper cleanup after each request"""
    if exception:
        db.session.rollback()
    db.session.remove()

@application.route('/open_whatsapp/<mobile>')
@login_required
def open_whatsapp(mobile):
    cleaned_mobile = ''.join(filter(str.isdigit, mobile))
    if len(cleaned_mobile) == 10:
        cleaned_mobile = '91' + cleaned_mobile
    
    user_agent = request.headers.get('User-Agent')
    if 'Mobile' in user_agent:
        whatsapp_url = f"whatsapp://send?phone={cleaned_mobile}"
    else:
        whatsapp_url = f"https://web.whatsapp.com/send?phone={cleaned_mobile}"
    
    return jsonify({'url': whatsapp_url})


@application.route('/api/call/history/<int:lead_id>', methods=['GET'])
@login_required
def call_history(lead_id):
    """
    Get call history for a specific lead
    """
    try:
        calls = CallLog.query.filter_by(lead_id=lead_id).order_by(CallLog.created_at.desc()).all()
        
        call_data = [{
            'call_sid': call.call_sid,
            'status': call.status,
            'duration': call.duration,
            'from_number': call.from_number,
            'to_number': call.to_number,
            'customer_number': call.customer_number,
            'direction': call.direction,
            'created_at': call.created_at.isoformat() if call.created_at else None,
            'user_name': call.user.name if call.user else 'Unknown'
        } for call in calls]
        
        return jsonify({
            'success': True,
            'calls': call_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@application.route('/api/call/stats', methods=['GET'])
@login_required
def call_stats():
    """
    Get call statistics for current user
    """
    try:
        date_from = request.args.get('from', datetime.now().strftime('%Y-%m-%d'))
        date_to = request.args.get('to', datetime.now().strftime('%Y-%m-%d'))
        
        # Parse dates
        from_date = datetime.strptime(date_from, '%Y-%m-%d')
        to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        
        # Get call statistics
        calls = CallLog.query.filter(
            CallLog.user_id == current_user.id,
            CallLog.created_at >= from_date,
            CallLog.created_at < to_date
        ).all()
        
        total_calls = len(calls)
        completed_calls = len([c for c in calls if c.status == 'completed'])
        failed_calls = len([c for c in calls if c.status in ['failed', 'busy', 'no-answer']])
        total_duration = sum([c.duration for c in calls if c.duration])
        avg_duration = total_duration / completed_calls if completed_calls > 0 else 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_calls': total_calls,
                'completed_calls': completed_calls,
                'failed_calls': failed_calls,
                'success_rate': (completed_calls / total_calls * 100) if total_calls > 0 else 0,
                'total_duration': total_duration,
                'avg_duration': round(avg_duration, 2)
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@application.route('/logout')
@login_required
def logout():
    logout_user()
    # Support both HTML redirect and JSON response
    accept_header = request.headers.get('Accept', '')
    if 'application/json' in accept_header:
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    return redirect(url_for('login'))

@application.route('/health')
def health_check():
    """Health check endpoint for AWS Elastic Beanstalk
    This endpoint is used by EB to determine application health.
    It should be fast and always return 200 OK to prevent false negatives.
    """
    try:
        # Quick database connectivity check (with timeout)
        # Use a simple query that's fast
        db.session.execute(text('SELECT 1')).fetchone()
        db.session.commit()
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.now(ist).isoformat()
        }), 200
    except Exception as e:
        # If database check fails, still return 200 but indicate database issue
        # This prevents health check from failing due to temporary DB issues
        # EB will mark as degraded but not as failed
        print(f"Health check database error: {str(e)}")
        return jsonify({
            'status': 'degraded',
            'database': 'disconnected',
            'message': 'Application is running but database connection failed',
            'timestamp': datetime.now(ist).isoformat()
        }), 200

@application.route('/')
def index():
    """Serve the Next.js frontend index page"""
    # The frontend will handle authentication via ProtectedRoute component
    return serve_frontend()

def utc_to_ist(utc_dt):
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    ist_tz = pytz.timezone('Asia/Kolkata')
    return utc_dt.astimezone(ist_tz)

def get_initial_followup_count(user_id, date):
    daily_count = DailyFollowupCount.query.filter_by(
        user_id=user_id, 
        date=date
    ).first()
    
    if daily_count:
        return daily_count.initial_count
    else:
        # Use timezone-aware datetime for proper comparison
        # Create IST datetime range for the date
        start_datetime_ist = ist.localize(datetime.combine(date, time.min))
        end_datetime_ist = start_datetime_ist + timedelta(days=1)
        # Convert to UTC for database query (followup_date is stored in UTC)
        start_datetime_utc = start_datetime_ist.astimezone(pytz.UTC)
        end_datetime_utc = end_datetime_ist.astimezone(pytz.UTC)
        
        current_count = Lead.query.filter(
            Lead.creator_id == user_id,
            Lead.followup_date >= start_datetime_utc,
            Lead.followup_date < end_datetime_utc
        ).count()
        
        # Create record
        daily_count = DailyFollowupCount(
            user_id=user_id,
            date=date,
            initial_count=current_count
        )
        try:
            db.session.add(daily_count)
            db.session.commit()
        except:
            db.session.rollback()
        
        return current_count

def capture_daily_snapshot():
    """
    Capture daily snapshot of followup counts at 5AM IST - this fixes the day's workload.
    
    This function:
    1. Counts all leads scheduled for today (followup_date = today) for each user
    2. Stores the initial_count in DailyFollowupCount table
    3. This count is used to calculate completion rates throughout the day
    4. Includes leads from previous days that have followup_date set for today
    """
    try:
        snapshot_time = datetime.now(ist)
        print(f"🔄 [SCHEDULER] Starting daily snapshot at {snapshot_time.strftime('%Y-%m-%d %H:%M:%S IST')}")
        
        # Get today's date in IST
        today = snapshot_time.date()
        today_start = ist.localize(datetime.combine(today, time.min))
        tomorrow_start = today_start + timedelta(days=1)
        
        # Convert to UTC for database queries
        today_start_utc = today_start.astimezone(pytz.UTC)
        tomorrow_start_utc = tomorrow_start.astimezone(pytz.UTC)
        
        print(f"📅 [SCHEDULER] Snapshot date: {today} (IST)")
        print(f"📅 [SCHEDULER] Time range: {today_start_utc} to {tomorrow_start_utc} (UTC)")
        
        # Get all users
        users = User.query.all()
        total_followups = 0
        user_snapshots = []
        
        for user in users:
            # Count leads scheduled for today for this user
            # This includes:
            # - Leads created today with followup_date = today
            # - Leads from previous days with followup_date = today (carried over)
            followup_count = Lead.query.filter(
                Lead.creator_id == user.id,
                Lead.followup_date >= today_start_utc,
                Lead.followup_date < tomorrow_start_utc
            ).count()
            
            # Also count leads by status for better tracking
            status_breakdown = db.session.query(
                Lead.status,
                db.func.count(Lead.id)
            ).filter(
                Lead.creator_id == user.id,
                Lead.followup_date >= today_start_utc,
                Lead.followup_date < tomorrow_start_utc
            ).group_by(Lead.status).all()
            
            status_summary = {status: count for status, count in status_breakdown}
            
            # Create or update the daily count record
            daily_count = DailyFollowupCount.query.filter_by(
                user_id=user.id,
                date=today
            ).first()
            
            old_count = daily_count.initial_count if daily_count else None
            
            if daily_count:
                # Update existing record - always override with current snapshot
                daily_count.initial_count = followup_count
                daily_count.created_at = snapshot_time  # Update timestamp
            else:
                # Create new record
                daily_count = DailyFollowupCount(
                    user_id=user.id,
                    date=today,
                    initial_count=followup_count,
                    created_at=snapshot_time
                )
                db.session.add(daily_count)
            
            total_followups += followup_count
            user_snapshots.append({
                'user': user.name,
                'count': followup_count,
                'old_count': old_count,
                'status_breakdown': status_summary
            })
            
            change_indicator = f" (was {old_count})" if old_count is not None and old_count != followup_count else ""
            print(f"✅ [SCHEDULER] User {user.name}: {followup_count} followups fixed for {today}{change_indicator}")
            if status_summary:
                print(f"   └─ Status breakdown: {status_summary}")
        
        db.session.commit()
        
        print(f"✅ [SCHEDULER] Daily snapshot completed successfully for {today}")
        print(f"📊 [SCHEDULER] Total followups across all users: {total_followups}")
        print(f"👥 [SCHEDULER] Users processed: {len(users)}")
        
        return {
            'success': True,
            'date': today.isoformat(),
            'timestamp': snapshot_time.isoformat(),
            'total_followups': total_followups,
            'users_processed': len(users),
            'user_snapshots': user_snapshots
        }
        
    except Exception as e:
        error_msg = f"❌ [SCHEDULER] Error in daily snapshot: {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now(ist).isoformat()
        }

# Initialize scheduler for daily snapshot (after function definition)
def init_scheduler():
    """
    Initialize and start the background scheduler for daily snapshots.
    
    The scheduler runs at 5:00 AM IST every day to:
    1. Capture initial followup counts for each user
    2. Store them in DailyFollowupCount table
    3. Fix the day's workload baseline for completion rate calculations
    
    Note: In production with gunicorn (multiple workers), the scheduler will run
    in each worker. This is acceptable for this use case as the snapshot function
    is idempotent (can run multiple times safely).
    """
    # Check if we should run the scheduler
    enable_scheduler = os.getenv('ENABLE_SCHEDULER', 'true').lower() == 'true'
    
    # Check if we're running under gunicorn (production)
    is_gunicorn = 'gunicorn' in os.environ.get('SERVER_SOFTWARE', '').lower() or \
                  'gunicorn' in ' '.join(sys.argv)
    
    print(f"🔧 [SCHEDULER] Initialization check:")
    print(f"   ENABLE_SCHEDULER={enable_scheduler}")
    print(f"   Running under gunicorn: {is_gunicorn}")
    
    if is_gunicorn and not enable_scheduler:
        print("ℹ️  [SCHEDULER] Scheduler disabled in gunicorn mode (set ENABLE_SCHEDULER=true to enable)")
        print("   Consider using a separate scheduler process or cron job for production")
        return None
    
    if not enable_scheduler:
        print("ℹ️  [SCHEDULER] Scheduler disabled via ENABLE_SCHEDULER=false")
        print("   Daily snapshot will need to be triggered manually via /api/trigger-snapshot")
        return None
    
    try:
        scheduler = BackgroundScheduler(timezone=ist)
        
        # Calculate next run time for display
        now_ist = datetime.now(ist)
        today_5am = ist.localize(datetime.combine(now_ist.date(), time(5, 0)))
        if now_ist >= today_5am:
            # If it's past 5 AM today, next run is tomorrow at 5 AM
            next_run = ist.localize(datetime.combine(now_ist.date() + timedelta(days=1), time(5, 0)))
        else:
            # Next run is today at 5 AM
            next_run = today_5am
        
        scheduler.add_job(
            func=capture_daily_snapshot,
            trigger=CronTrigger(hour=5, minute=0, timezone=ist),  # 5:00 AM IST daily
            id='daily_snapshot_job',
            name='Daily Followup Snapshot at 5 AM IST',
            replace_existing=True
        )
        scheduler.start()
        
        print("✅ [SCHEDULER] Daily snapshot scheduler started successfully")
        print(f"   ⏰ Scheduled to run daily at 5:00 AM IST")
        print(f"   📅 Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S IST')}")
        print(f"   ⏳ Time until next run: {next_run - now_ist}")
        print(f"   📊 This will capture initial followup counts for completion rate tracking")
        
        return scheduler
    except Exception as e:
        print(f"⚠️  [SCHEDULER] Failed to start scheduler: {e}")
        import traceback
        traceback.print_exc()
        print("   Daily snapshot will need to be triggered manually via /api/trigger-snapshot")
        return None

def record_worked_lead(lead_id, user_id, old_followup_date, new_followup_date):
    """
    Record when a lead has been worked upon by changing its followup date.
    This is used to track completion rates and user performance.
    """
    try:
        # Get today's date in IST
        today = datetime.now(ist).date()
        
        # Check if we already have a record for this lead on this day
        existing_record = WorkedLead.query.filter_by(
            lead_id=lead_id,
            user_id=user_id,
            work_date=today
        ).first()
        
        if not existing_record:
            # Create new worked lead record
            worked_lead = WorkedLead(
                lead_id=lead_id,
                user_id=user_id,
                work_date=today,
                old_followup_date=old_followup_date,
                new_followup_date=new_followup_date,
                worked_at=datetime.now(ist)
            )
            db.session.add(worked_lead)
            db.session.commit()
            print(f"Recorded worked lead: Lead {lead_id} by User {user_id} on {today}")
        else:
            # Update existing record with new followup date
            existing_record.new_followup_date = new_followup_date
            existing_record.worked_at = datetime.now(ist)
            db.session.commit()
            print(f"Updated worked lead: Lead {lead_id} by User {user_id} on {today}")
        
    except Exception as e:
        print(f"Error recording worked lead: {e}")
        db.session.rollback()

def get_worked_leads_for_date(user_id, date):
    """
    Get the count of worked leads for a specific user on a specific date.
    Only counts leads that were part of the initial assignment (old_followup_date was on target date).
    This ensures completion rate is calculated correctly: worked leads / initial assignment.
    """
    try:
        # Create IST datetime range for the target date
        date_start_ist = ist.localize(datetime.combine(date, time.min))
        date_end_ist = date_start_ist + timedelta(days=1)
        # Convert to UTC for database query (old_followup_date is stored in UTC)
        date_start_utc = date_start_ist.astimezone(pytz.UTC)
        date_end_utc = date_end_ist.astimezone(pytz.UTC)
        
        # Count only worked leads where:
        # 1. The work was done on the target date (work_date = date)
        # 2. The lead's old_followup_date was on the target date (was part of initial assignment)
        # 3. old_followup_date is not None (exclude leads that didn't have a followup date before)
        worked_count = WorkedLead.query.filter(
            WorkedLead.user_id == user_id,
            WorkedLead.work_date == date,
            WorkedLead.old_followup_date.isnot(None),
            WorkedLead.old_followup_date >= date_start_utc,
            WorkedLead.old_followup_date < date_end_utc
        ).count()
        return worked_count
    except Exception as e:
        print(f"Error getting worked leads count: {e}")
        import traceback
        traceback.print_exc()
        return 0

def calculate_completion_rate(initial_count, worked_count):
    """
    Calculate completion rate as a percentage.
    """
    if initial_count == 0:
        return 0
    return round((worked_count / initial_count) * 100, 1)

@application.route('/add_lead', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def add_lead():
    # Check if this is an API request from Next.js frontend
    # Next.js frontend sends form data but we can detect it by checking Origin/Referer
    is_api_request = (
        request.headers.get('Accept', '').startswith('application/json') or
        request.headers.get('Content-Type', '').startswith('application/json') or
        request.headers.get('Origin', '').endswith('.gaadimech.com') or
        'crm.gaadimech.com' in request.headers.get('Referer', '') or
        'localhost:3000' in request.headers.get('Origin', '')
    )
    
    try:
        customer_name = request.form.get('customer_name')
        mobile = request.form.get('mobile')
        car_registration = request.form.get('car_registration')
        car_model = request.form.get('car_model')
        remarks = request.form.get('remarks')
        status = request.form.get('status')

        if not status or status not in ['New Lead', 'Did Not Pick Up', 'Needs Followup', 'Confirmed', 'Open', 'Completed', 'Feedback', 'Dead Lead']:
            status = 'New Lead'

        # Parse followup_date as YYYY-MM-DD and create at midnight IST, then convert to UTC
        followup_date_str = request.form.get('followup_date')
        followup_date_only = datetime.strptime(followup_date_str, '%Y-%m-%d').date()
        followup_date = ist.localize(datetime.combine(followup_date_only, datetime.min.time())).astimezone(pytz.UTC)

        if not all([customer_name, mobile, followup_date]):
            if is_api_request:
                return jsonify({'success': False, 'error': 'All required fields must be filled'}), 400
            flash('All required fields must be filled', 'error')
            return redirect(url_for('index'))

        # Normalize mobile number
        normalized_mobile = normalize_mobile_number(mobile)
        if not normalized_mobile:
            if is_api_request:
                return jsonify({'success': False, 'error': 'Invalid mobile number format. Please use: +917404625111, 7404625111, or 917404625111'}), 400
            flash('Invalid mobile number format. Please use: +917404625111, 7404625111, or 917404625111', 'error')
            return redirect(url_for('index'))
        mobile = normalized_mobile

        new_lead = Lead(
            customer_name=customer_name,
            mobile=mobile,
            car_registration=car_registration,
            car_model=car_model.strip() if car_model else None,
            followup_date=followup_date,
            remarks=remarks,
            status=status,
            creator_id=current_user.id,
            created_at=datetime.now(ist),
            modified_at=datetime.now(ist)
        )
        
        db.session.add(new_lead)
        db.session.commit()
        
        # Clear any cached queries to ensure dashboard gets fresh data
        db.session.expire_all()
        
        if is_api_request:
            return jsonify({'success': True, 'message': 'Lead added successfully!', 'lead_id': new_lead.id}), 200
        
        flash('Lead added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        error_msg = f'Error adding lead: {str(e)}'
        print(error_msg)
        if is_api_request:
            return jsonify({'success': False, 'error': 'Error adding lead. Please try again.'}), 500
        flash('Error adding lead. Please try again.', 'error')
    
    # For non-API requests (old template), return redirect
    return redirect(url_for('index'))

@application.route('/edit_lead/<int:lead_id>', methods=['GET', 'POST'])
@login_required
def edit_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    
    # Check permissions
    if not current_user.is_admin and lead.creator_id != current_user.id:
        flash('Permission denied', 'error')
        return redirect(url_for('followups'))
    
    if request.method == 'POST':
        try:
            # Store old followup date for tracking
            old_followup_date = lead.followup_date
            
            lead.customer_name = request.form.get('customer_name')
            # Normalize mobile number
            mobile = request.form.get('mobile')
            if mobile:
                normalized_mobile = normalize_mobile_number(mobile)
                if not normalized_mobile:
                    flash('Invalid mobile number format. Please use: +917404625111, 7404625111, or 917404625111', 'error')
                    return render_template('edit_lead.html', lead=lead)
                lead.mobile = normalized_mobile
            lead.car_registration = request.form.get('car_registration')
            lead.car_model = request.form.get('car_model')
            lead.remarks = request.form.get('remarks')
            lead.status = request.form.get('status')
            
            # Handle followup date
            followup_date = datetime.strptime(request.form.get('followup_date'), '%Y-%m-%d')
            new_followup_date = ist.localize(followup_date)
            lead.followup_date = new_followup_date
            lead.modified_at = datetime.now(ist)
            
            db.session.commit()
            
            # Record that this lead has been worked upon only if followup date changed
            if old_followup_date != new_followup_date:
                record_worked_lead(lead.id, current_user.id, old_followup_date, new_followup_date)
            
            # Clear any cached queries to ensure dashboard gets fresh data
            db.session.expire_all()
            
            flash('Lead updated successfully!', 'success')
            return redirect(url_for('followups'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating lead', 'error')
            print(f"Error updating lead: {str(e)}")
    
    return render_template('edit_lead.html', lead=lead)

@application.route('/delete_lead/<int:lead_id>', methods=['POST'])
@login_required
def delete_lead(lead_id):
    try:
        lead = Lead.query.get_or_404(lead_id)
        
        # Check permissions - only admin or creator can delete
        if not current_user.is_admin and lead.creator_id != current_user.id:
            return jsonify({'success': False, 'message': 'Permission denied'})
        
        # Delete the lead
        db.session.delete(lead)
        db.session.commit()
        
        # Clear any cached queries to ensure dashboard gets fresh data
        db.session.expire_all()
        
        return jsonify({'success': True, 'message': 'Lead deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting lead: {str(e)}")
        return jsonify({'success': False, 'message': 'Error deleting lead'})

@application.route('/api/dashboard/status-update', methods=['POST'])
@login_required
def update_lead_status():
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        new_status = data.get('status')
        
        lead = Lead.query.get_or_404(lead_id)
        
        # Check permissions
        if not current_user.is_admin and lead.creator_id != current_user.id:
            return jsonify({'success': False, 'message': 'Permission denied'})
        
        lead.status = new_status
        lead.modified_at = datetime.now(ist)
        db.session.commit()
        
        # Clear any cached queries to ensure dashboard gets fresh data
        db.session.expire_all()
        
        return jsonify({'success': True, 'message': 'Status updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating status: {str(e)}")
        return jsonify({'success': False, 'message': 'Error updating status'})

@application.route('/api/dashboard/quick-followup', methods=['POST'])
@login_required
def add_quick_followup():
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        followup_date = data.get('followup_date')
        remarks = data.get('remarks', '')
        
        lead = Lead.query.get_or_404(lead_id)
        
        # Check permissions
        if not current_user.is_admin and lead.creator_id != current_user.id:
            return jsonify({'success': False, 'message': 'Permission denied'})
        
        # Store old followup date for tracking
        old_followup_date = lead.followup_date
        
        # Update followup date
        followup_datetime = datetime.strptime(followup_date, '%Y-%m-%d')
        new_followup_date = ist.localize(followup_datetime)
        lead.followup_date = new_followup_date
        if remarks:
            lead.remarks = remarks
        lead.modified_at = datetime.now(ist)
        
        db.session.commit()
        
        # Record that this lead has been worked upon
        record_worked_lead(lead_id, current_user.id, old_followup_date, new_followup_date)
        
        # Clear any cached queries to ensure dashboard gets fresh data
        db.session.expire_all()
        
        return jsonify({'success': True, 'message': 'Followup scheduled successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error scheduling followup: {str(e)}")
        return jsonify({'success': False, 'message': 'Error scheduling followup'})

@application.route('/api/trigger-snapshot', methods=['POST'])
@login_required
def trigger_manual_snapshot():
    """Manual trigger for daily snapshot - useful for testing or emergency fixes"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        result = capture_daily_snapshot()
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Daily snapshot completed successfully',
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Error: {result.get("error", "Unknown error")}',
                'data': result
            })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@application.route('/api/scheduler/status', methods=['GET'])
@login_required
def scheduler_status():
    """Check scheduler status and last snapshot information"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        # Check if scheduler is enabled
        enable_scheduler = os.getenv('ENABLE_SCHEDULER', 'true').lower() == 'true'
        
        # Get today's snapshot
        today = datetime.now(ist).date()
        today_snapshot = DailyFollowupCount.query.filter_by(date=today).all()
        
        # Get yesterday's snapshot for comparison
        yesterday = today - timedelta(days=1)
        yesterday_snapshot = DailyFollowupCount.query.filter_by(date=yesterday).all()
        
        # Get most recent snapshot timestamp
        most_recent = DailyFollowupCount.query.order_by(
            DailyFollowupCount.created_at.desc()
        ).first()
        
        # Check next scheduled run (5 AM IST tomorrow)
        tomorrow_5am = ist.localize(datetime.combine(today + timedelta(days=1), time(5, 0)))
        next_run = tomorrow_5am
        
        # If it's before 5 AM today, next run is today at 5 AM
        now_ist = datetime.now(ist)
        today_5am = ist.localize(datetime.combine(today, time(5, 0)))
        if now_ist < today_5am:
            next_run = today_5am
        
        status_data = {
            'scheduler_enabled': enable_scheduler,
            'current_time_ist': now_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
            'today': today.isoformat(),
            'today_snapshot': {
                'exists': len(today_snapshot) > 0,
                'user_count': len(today_snapshot),
                'total_initial_followups': sum(s.initial_count for s in today_snapshot),
                'details': [
                    {
                        'user_id': s.user_id,
                        'user_name': User.query.get(s.user_id).name if User.query.get(s.user_id) else 'Unknown',
                        'initial_count': s.initial_count,
                        'snapshot_time': s.created_at.strftime('%Y-%m-%d %H:%M:%S IST') if s.created_at else None
                    }
                    for s in today_snapshot
                ]
            },
            'yesterday_snapshot': {
                'exists': len(yesterday_snapshot) > 0,
                'user_count': len(yesterday_snapshot),
                'total_initial_followups': sum(s.initial_count for s in yesterday_snapshot) if yesterday_snapshot else 0
            },
            'most_recent_snapshot': {
                'date': most_recent.date.isoformat() if most_recent else None,
                'timestamp': most_recent.created_at.strftime('%Y-%m-%d %H:%M:%S IST') if most_recent and most_recent.created_at else None
            },
            'next_scheduled_run': next_run.strftime('%Y-%m-%d %H:%M:%S IST'),
            'time_until_next_run': str(next_run - now_ist) if next_run > now_ist else 'Past due'
        }
        
        return jsonify({
            'success': True,
            'status': status_data
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error checking scheduler status: {str(e)}'
        })

@application.route('/api/export-mobile-numbers', methods=['GET'])
@login_required
def export_mobile_numbers():
    """Export mobile numbers based on followup date and team member filters"""
    try:
        # Get query parameters
        selected_date = request.args.get('date', datetime.now(ist).strftime('%Y-%m-%d'))
        selected_user_id = request.args.get('user_id', '')
        
        # Parse the selected date
        target_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
        target_end = target_start + timedelta(days=1)
        
        # Convert to UTC for database queries
        target_start_utc = target_start.astimezone(pytz.UTC)
        target_end_utc = target_end.astimezone(pytz.UTC)
        
        # Build query based on filters
        query = Lead.query.filter(
            Lead.followup_date >= target_start_utc,
            Lead.followup_date < target_end_utc
        )
        
        # Apply user filter if specified
        if current_user.is_admin and selected_user_id:
            try:
                user_id = int(selected_user_id)
                query = query.filter(Lead.creator_id == user_id)
            except ValueError:
                pass  # Invalid user ID, show all
        elif not current_user.is_admin:
            # Non-admin users can only see their own followups
            query = query.filter(Lead.creator_id == current_user.id)
        
        # Get the followups
        followups = query.order_by(Lead.customer_name).all()
        
        # Extract mobile numbers
        mobile_numbers = []
        for followup in followups:
            mobile_numbers.append({
                'mobile': followup.mobile,
                'customer_name': followup.customer_name,
                'car_registration': followup.car_registration or '',
                'status': followup.status,
                'created_by': followup.creator.name if followup.creator else 'Unknown'
            })
        
        # Prepare CSV data
        csv_header = 'Mobile Number,Customer Name,Car Registration,Status,Created By\n'
        csv_data = csv_header
        
        for item in mobile_numbers:
            csv_data += f"{item['mobile']},{item['customer_name']},{item['car_registration']},{item['status']},{item['created_by']}\n"
        
        # Return response
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=mobile_numbers_{selected_date}.csv'
        
        return response
        
    except Exception as e:
        print(f"Error exporting mobile numbers: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@application.route('/api/parse-customer-text', methods=['POST'])
@login_required
def parse_customer_text_api():
    """Parse customer information from text messages"""
    try:
        # Check if user is admin
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
        
        # Get the text from request
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'success': False, 'message': 'No text provided'}), 400
        
        text = data['text'].strip()
        if not text:
            return jsonify({'success': False, 'message': 'Empty text provided'}), 400
        
        # Parse the text
        parsed_info = parse_customer_text(text)
        
        # If customer name is missing, get the next default customer name from database
        if not parsed_info.get('customer_name') or not parsed_info['customer_name'].strip():
            default_name = get_next_default_customer_name()
            parsed_info['customer_name'] = default_name
        
        # Return the parsed information
        return jsonify({
            'success': True,
            'data': parsed_info,
            'message': 'Text parsed successfully'
        })
        
    except Exception as e:
        print(f"Error parsing customer text: {e}")
        return jsonify({'success': False, 'message': f'Error parsing text: {str(e)}'})

@application.route('/api/customer-name/next', methods=['GET'])
@login_required
def get_next_customer_name():
    """Get the next default customer name with atomic counter increment"""
    try:
        # Check if user is admin
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
        
        default_name = get_next_default_customer_name()
        
        return jsonify({
            'success': True,
            'customer_name': default_name,
            'message': 'Next customer name generated successfully'
        })
        
    except Exception as e:
        print(f"Error getting next customer name: {e}")
        return jsonify({'success': False, 'message': f'Error generating customer name: {str(e)}'})

def get_next_default_customer_name():
    """
    Atomically increment the customer name counter and return the next default name.
    Uses database-level locking to ensure thread-safety across multiple users.
    """
    try:
        # Use a transaction with row-level locking to ensure atomicity
        # This prevents race conditions when multiple users request names simultaneously
        # with_for_update() locks the row until the transaction completes
        counter_row = CustomerNameCounter.query.with_for_update().first()
        
        if not counter_row:
            # First time - create the counter row
            counter_row = CustomerNameCounter(counter=0)
            db.session.add(counter_row)
            db.session.flush()  # Flush to get the ID
        
        # Increment the counter atomically
        counter_row.counter += 1
        counter_row.updated_at = datetime.now(ist)
        
        # Get the new counter value
        new_counter = counter_row.counter
        
        # Commit the transaction
        db.session.commit()
        
        return f"Customer {new_counter}"
            
    except Exception as e:
        db.session.rollback()
        print(f"Error in get_next_default_customer_name: {e}")
        # Fallback: use timestamp if database fails
        return f"Customer {int(datetime.now().timestamp())}"

@application.route('/api/user-followup-numbers/<int:user_id>', methods=['GET'])
@login_required
def get_user_followup_numbers(user_id):
    """Get followup numbers for a specific user to send via WhatsApp"""
    try:
        # Check if user is admin
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403
        
        # Get the user
        user = User.query.get_or_404(user_id)
        
        # Get user's mobile number from mapping
        user_mobile = USER_MOBILE_MAPPING.get(user.name, None)
        
        if not user_mobile:
            return jsonify({'success': False, 'message': f'No mobile number found for {user.name}'})
        
        # Get today's date
        today = datetime.now(ist).date()
        target_start = ist.localize(datetime.combine(today, datetime.min.time()))
        target_end = target_start + timedelta(days=1)
        target_start_utc = target_start.astimezone(pytz.UTC)
        target_end_utc = target_end.astimezone(pytz.UTC)
        
        # Get user's followups for today
        followups = Lead.query.filter(
            Lead.creator_id == user_id,
            Lead.followup_date >= target_start_utc,
            Lead.followup_date < target_end_utc
        ).order_by(Lead.customer_name).all()
        
        # Format followup data
        followup_data = []
        for followup in followups:
            followup_data.append({
                'customer_name': followup.customer_name,
                'mobile': followup.mobile,
                'car_registration': followup.car_registration or '',
                'status': followup.status,
                'remarks': followup.remarks or ''
            })
        
        return jsonify({
            'success': True,
            'user_name': user.name,
            'user_mobile': user_mobile,
            'total_followups': len(followup_data),
            'followups': followup_data
        })
        
    except Exception as e:
        print(f"Error getting user followup numbers: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@application.route('/dashboard')
def dashboard():
    # Only serve Flask template for API requests, otherwise serve Next.js
    is_api_request = request.headers.get('Accept', '').startswith('application/json')
    if is_api_request and not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    if is_api_request:
        # This would be handled by API routes, but for now serve Next.js
        pass
    # For page requests, serve Next.js frontend
    return serve_frontend()

@application.route('/dashboard-old')
@login_required
def dashboard_old():
    try:
        # Get query parameters
        selected_date = request.args.get('date', datetime.now(ist).strftime('%Y-%m-%d'))
        selected_user_id = request.args.get('user_id', '')
        
        # Parse the selected date
        try:
            target_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
            target_end = target_start + timedelta(days=1)
        except ValueError:
            target_date = datetime.now(ist).date()
            target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
            target_end = target_start + timedelta(days=1)
            selected_date = target_date.strftime('%Y-%m-%d')
        
        # Convert to UTC for database queries
        target_start_utc = target_start.astimezone(pytz.UTC)
        target_end_utc = target_end.astimezone(pytz.UTC)
        
        # Get users based on permissions
        if current_user.is_admin:
            users = User.query.all()
        else:
            users = [current_user]
            selected_user_id = str(current_user.id)
        
        # Base query setup with user filtering
        base_conditions = []
        if selected_user_id and current_user.is_admin:
            try:
                base_conditions.append(Lead.creator_id == int(selected_user_id))
            except ValueError:
                pass
        elif not current_user.is_admin:
            base_conditions.append(Lead.creator_id == current_user.id)
        
        # Get current followups for the selected date
        current_followups_query = db.session.query(Lead).filter(
            Lead.followup_date >= target_start_utc,
            Lead.followup_date < target_end_utc
        )
        if base_conditions:
            current_followups_query = current_followups_query.filter(*base_conditions)
        
        # Add status ordering: New Lead > Feedback > Confirmed > Open > Completed > Needs Followup > Did not Pick up > Dead Lead
        status_order = db.case(
            (Lead.status == 'New Lead', 0),
            (Lead.status == 'Feedback', 1),
            (Lead.status == 'Confirmed', 2),
            (Lead.status == 'Open', 3),
            (Lead.status == 'Completed', 4),
            (Lead.status == 'Needs Followup', 5),
            (Lead.status == 'Did Not Pick Up', 6),
            (Lead.status == 'Dead Lead', 7),
            else_=8
        )
        current_followups = current_followups_query.order_by(status_order.asc(), Lead.followup_date.asc()).all()
        
        # Convert followups to IST for display
        for followup in current_followups:
            if followup.followup_date:
                followup.followup_date = utc_to_ist(followup.followup_date)
            if followup.created_at:
                followup.created_at = utc_to_ist(followup.created_at)
            if followup.modified_at:
                followup.modified_at = utc_to_ist(followup.modified_at)
        
        # Get daily leads count
        daily_leads_count_query = db.session.query(db.func.count(Lead.id)).filter(
            Lead.created_at >= target_start_utc,
            Lead.created_at < target_end_utc
        )
        if base_conditions:
            daily_leads_count_query = daily_leads_count_query.filter(*base_conditions)
        
        daily_leads_count = daily_leads_count_query.scalar() or 0
        
        # Get status counts
        status_counts_query = db.session.query(
            Lead.status,
            db.func.count(Lead.id)
        ).group_by(Lead.status)
        
        if base_conditions:
            status_counts_query = status_counts_query.filter(*base_conditions)
        
        status_counts = dict(status_counts_query.all())
        
        # Get total leads count
        total_leads_query = db.session.query(db.func.count(Lead.id))
        if base_conditions:
            total_leads_query = total_leads_query.filter(*base_conditions)
        
        total_leads = total_leads_query.scalar() or 0
        
        # Calculate user performance
        user_performance_list = []
        for user in users:
            # Get user's followups for today
            user_followups = [f for f in current_followups if f.creator_id == user.id]
            
            # Get initial followup count from 5AM snapshot
            initial_count = get_initial_followup_count(user.id, target_date)
            
            # Get worked leads count for today
            worked_count = get_worked_leads_for_date(user.id, target_date)
            
            # Calculate completion rate
            completion_rate = calculate_completion_rate(initial_count, worked_count)
            
            # Calculate pending count
            pending_count = max(0, initial_count - worked_count)
            
            # Get user's total leads
            user_total = db.session.query(db.func.count(Lead.id)).filter(
                Lead.creator_id == user.id
            ).scalar() or 0
            
            # Get user's status counts
            user_status_counts = dict(
                db.session.query(
                    Lead.status,
                    db.func.count(Lead.id)
                ).filter(
                    Lead.creator_id == user.id
                ).group_by(Lead.status).all()
            )
            
            # Get new leads count for the selected date
            new_leads_count = db.session.query(db.func.count(Lead.id)).filter(
                Lead.creator_id == user.id,
                Lead.created_at >= target_start_utc,
                Lead.created_at < target_end_utc
            ).scalar() or 0
            
            user_performance_list.append({
                'user': user,
                'initial_followups': initial_count,
                'pending_followups': pending_count,
                'worked_followups': worked_count,
                'completion_rate': completion_rate,
                'leads_created': user_total,
             
                'completed': user_status_counts.get('Completed', 0),
                'assigned': initial_count,
                'worked': worked_count,
                'pending': pending_count,
                'new_additions': new_leads_count,  # Update with actual new leads count
                'original_assignment': initial_count
            })
        
        # Sort by completion rate
        user_performance_list.sort(key=lambda x: (x['completion_rate'], x['initial_followups']), reverse=True)
        
        # Calculate overall metrics
        total_initial_count = sum(perf['initial_followups'] for perf in user_performance_list)
        total_worked_count = sum(perf['worked_followups'] for perf in user_performance_list)
        overall_completion_rate = calculate_completion_rate(total_initial_count, total_worked_count)
        
        return render_template('dashboard.html',
            todays_followups=current_followups,
            daily_leads_count=daily_leads_count,
            user_performance=user_performance_list,
            status_counts=status_counts,
            users=users,
            selected_date=selected_date,
            selected_user_id=selected_user_id,
            total_leads=total_leads,
            followup_efficiency=0,
            initial_followups_count=total_initial_count,
            completion_rate=overall_completion_rate,
            completed_followups=total_worked_count,
            current_pending_count=len(current_followups),
            USER_MOBILE_MAPPING=USER_MOBILE_MAPPING
        )
        
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        flash('Dashboard temporarily unavailable. Please try again.', 'error')
        return redirect(url_for('index'))

@application.route('/api/dashboard/followup/<int:lead_id>', methods=['GET'])
@login_required
def get_followup_details(lead_id):
    try:
        lead = Lead.query.get_or_404(lead_id)
        
        # Check permissions
        if not current_user.is_admin and lead.creator_id != current_user.id:
            return jsonify({'success': False, 'message': 'Permission denied'})
        
        # Convert followup date to IST for display
        followup_date = utc_to_ist(lead.followup_date) if lead.followup_date else None
        
        return jsonify({
            'success': True,
            'customer_name': lead.customer_name,
            'mobile': lead.mobile,
            'car_registration': lead.car_registration,
            'car_model': lead.car_model,
            'followup_date': followup_date.strftime('%Y-%m-%d') if followup_date else None,
            'status': lead.status,
            'remarks': lead.remarks
        })
        
    except Exception as e:
        print(f"Error fetching followup details: {e}")
        return jsonify({'success': False, 'message': 'Error fetching followup details'})

@application.route('/api/dashboard/update-followup', methods=['POST'])
@login_required
def update_followup():
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        customer_name = data.get('customer_name')
        mobile = data.get('mobile')
        car_registration = data.get('car_registration')
        followup_date = data.get('followup_date')
        status = data.get('status')
        remarks = data.get('remarks')
        
        lead = Lead.query.get_or_404(lead_id)
        
        # Check permissions
        if not current_user.is_admin and lead.creator_id != current_user.id:
            return jsonify({'success': False, 'message': 'Permission denied'})
        
        # Store old followup date for tracking
        old_followup_date = lead.followup_date
        
        # Update lead details
        lead.customer_name = customer_name
        # Normalize mobile number
        if mobile:
            normalized_mobile = normalize_mobile_number(mobile)
            if not normalized_mobile:
                return jsonify({'success': False, 'message': 'Invalid mobile number format. Please use: +917404625111, 7404625111, or 917404625111'}), 400
            lead.mobile = normalized_mobile
        lead.car_registration = car_registration
        
        # Update followup date
        followup_datetime = datetime.strptime(followup_date, '%Y-%m-%d')
        new_followup_date = ist.localize(followup_datetime)
        lead.followup_date = new_followup_date
        
        lead.status = status
        lead.remarks = remarks
        lead.modified_at = datetime.now(ist)
        
        db.session.commit()
        
        # Record that this lead has been worked upon if followup date changed
        if old_followup_date != new_followup_date:
            record_worked_lead(lead_id, current_user.id, old_followup_date, new_followup_date)
        
        # Clear any cached queries to ensure dashboard gets fresh data
        db.session.expire_all()
        
        return jsonify({'success': True, 'message': 'Followup updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating followup: {e}")
        return jsonify({'success': False, 'message': 'Error updating followup'})

# Priority 1: Core API endpoints for new TypeScript frontend

@application.route('/api/followups/today', methods=['GET'])
@login_required
def api_followups_today():
    """Get today's followups queue with optional filters"""
    try:
        # Ensure database connection
        db.session.execute(db.text('SELECT 1'))
        # Get query parameters
        date_str = request.args.get('date', datetime.now(ist).strftime('%Y-%m-%d'))
        overdue_only = request.args.get('overdue_only', '0') == '1'
        user_id_param = request.args.get('user_id', '')
        
        # Parse the date
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = datetime.now(ist).date()
        
        # Create IST datetime range for the selected date
        # Start: selected date at 00:00:00 IST
        # End: selected date at 23:59:59.999 IST (next day 00:00:00 IST)
        target_start_ist = ist.localize(datetime.combine(target_date, datetime.min.time()))
        target_end_ist = target_start_ist + timedelta(days=1)
        
        # Convert to UTC for database query
        # This ensures we get all followups that fall on the selected date in IST
        target_start_utc = target_start_ist.astimezone(pytz.UTC)
        target_end_utc = target_end_ist.astimezone(pytz.UTC)
        
        # Debug logging
        print(f"Date filter - Selected: {date_str} ({target_date})")
        print(f"  IST range: {target_start_ist} to {target_end_ist}")
        print(f"  UTC range: {target_start_utc} to {target_end_utc}")
        
        # Build query - filter by UTC range
        # This will correctly include all followups that fall on the selected date in IST
        query = Lead.query.filter(
            Lead.followup_date >= target_start_utc,
            Lead.followup_date < target_end_utc
        )
        
        # Apply user filter
        if user_id_param and current_user.is_admin:
            try:
                query = query.filter(Lead.creator_id == int(user_id_param))
            except ValueError:
                pass
        elif not current_user.is_admin:
            query = query.filter(Lead.creator_id == current_user.id)
        
        # Status priority order: New Lead > Feedback > Confirmed > Open > Completed > Needs Followup > Did Not Pick Up > Dead Lead
        status_order = db.case(
            (Lead.status == 'New Lead', 0),
            (Lead.status == 'Feedback', 1),
            (Lead.status == 'Confirmed', 2),
            (Lead.status == 'Open', 3),
            (Lead.status == 'Completed', 4),
            (Lead.status == 'Needs Followup', 5),
            (Lead.status == 'Did Not Pick Up', 6),
            (Lead.status == 'Dead Lead', 7),
            else_=8
        )
        
        # Get leads - order by status priority first, then by followup_date ascending
        leads = query.order_by(status_order.asc(), Lead.followup_date.asc()).all()
        
        # Convert to JSON format
        items = []
        now_utc = datetime.now(pytz.UTC)
        
        for lead in leads:
            # Check if overdue - ensure both datetimes are timezone-aware
            if lead.followup_date:
                # Ensure followup_date is timezone-aware (it should be UTC from DB)
                if lead.followup_date.tzinfo is None:
                    # If naive, assume it's UTC
                    followup_date_aware = pytz.UTC.localize(lead.followup_date)
                else:
                    followup_date_aware = lead.followup_date
                is_overdue = followup_date_aware < now_utc
            else:
                is_overdue = False
            
            # Skip if overdue_only filter is set and lead is not overdue
            if overdue_only and not is_overdue:
                continue
            
            # Get creator name
            creator_name = lead.creator.name if lead.creator else 'Unknown'
            
            # Ensure followup_date is timezone-aware before converting to ISO
            followup_date_iso = None
            if lead.followup_date:
                # If naive, assume it's UTC and localize it
                if lead.followup_date.tzinfo is None:
                    followup_date_aware = pytz.UTC.localize(lead.followup_date)
                else:
                    followup_date_aware = lead.followup_date
                followup_date_iso = followup_date_aware.isoformat()
            
            items.append({
                'id': lead.id,
                'customer_name': lead.customer_name,
                'mobile': lead.mobile,
                'car_registration': lead.car_registration or '',
                'car_model': lead.car_model or '',
                'followup_date': followup_date_iso,
                'status': lead.status,
                'remarks': lead.remarks or '',
                'creator_id': lead.creator_id,
                'creator_name': creator_name,
                'created_at': lead.created_at.isoformat() if lead.created_at else None,
                'modified_at': lead.modified_at.isoformat() if lead.modified_at else None,
                'overdue': is_overdue
            })
        
        return jsonify({
            'date': date_str,
            'items': items
        })
        
    except Exception as e:
        print(f"Error in api_followups_today: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'message': 'Failed to fetch followups'}), 500

@application.route('/api/dashboard/metrics', methods=['GET'])
@login_required
def api_dashboard_metrics():
    """Get dashboard metrics for a specific date"""
    try:
        # Ensure database connection
        db.session.execute(db.text('SELECT 1'))
        date_str = request.args.get('date', datetime.now(ist).strftime('%Y-%m-%d'))
        
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = datetime.now(ist).date()
        
        target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
        target_end = target_start + timedelta(days=1)
        target_start_utc = target_start.astimezone(pytz.UTC)
        target_end_utc = target_end.astimezone(pytz.UTC)
        
        # Get user_id filter (only for admins)
        user_id_param = request.args.get('user_id', '')
        filter_user_id = None
        if user_id_param and current_user.is_admin:
            try:
                filter_user_id = int(user_id_param)
            except ValueError:
                pass
        
        # Base conditions for user filtering
        base_conditions = []
        if filter_user_id:
            # Admin filtering by specific user
            base_conditions.append(Lead.creator_id == filter_user_id)
        elif not current_user.is_admin:
            # Non-admin sees only their own data
            base_conditions.append(Lead.creator_id == current_user.id)
        
        # Today's followups count - current count of leads with followup_date = target_date
        # Note: This shows leads that CURRENTLY have today's date, which may be less than
        # the initial assignment if leads have been worked on and moved to different dates
        todays_followups_query = db.session.query(db.func.count(Lead.id)).filter(
            Lead.followup_date >= target_start_utc,
            Lead.followup_date < target_end_utc
        )
        if base_conditions:
            todays_followups_query = todays_followups_query.filter(*base_conditions)
        todays_followups = todays_followups_query.scalar() or 0
        
        # Pending followups (status not Completed/Confirmed/Dead Lead)
        pending_query = db.session.query(db.func.count(Lead.id)).filter(
            Lead.followup_date >= target_start_utc,
            Lead.followup_date < target_end_utc,
            ~Lead.status.in_(['Completed', 'Confirmed', 'Dead Lead'])
        )
        if base_conditions:
            pending_query = pending_query.filter(*base_conditions)
        pending_followups = pending_query.scalar() or 0
        
        # Initial assignment (from daily snapshot taken at 5AM IST)
        # This is a fixed snapshot of how many leads were scheduled for this date at the start of the day
        # The difference between initial_assignment and todays_followups represents leads that have been
        # worked on and had their followup_date changed to a different date
        if filter_user_id:
            # Filter by specific user
            users = User.query.filter_by(id=filter_user_id).all()
        elif current_user.is_admin:
            users = User.query.all()
        else:
            users = [current_user]
        
        total_initial_count = 0
        total_worked_count = 0
        
        for user in users:
            initial_count = get_initial_followup_count(user.id, target_date)
            worked_count = get_worked_leads_for_date(user.id, target_date)
            total_initial_count += initial_count
            total_worked_count += worked_count
        
        # New leads today
        new_leads_query = db.session.query(db.func.count(Lead.id)).filter(
            Lead.created_at >= target_start_utc,
            Lead.created_at < target_end_utc
        )
        if base_conditions:
            new_leads_query = new_leads_query.filter(*base_conditions)
        new_leads_today = new_leads_query.scalar() or 0
        
        # Completion rate
        completion_rate = calculate_completion_rate(total_initial_count, total_worked_count)
        
        # Team leads statistics (for non-admin users, show their own assigned leads)
        team_leads_stats = {
            'total_assigned': 0,
            'pending': 0,
            'contacted': 0,
            'added_to_crm': 0
        }
        
        # Get team leads for the selected date
        team_leads_query = TeamAssignment.query.filter(
            TeamAssignment.assigned_date == target_date
        )
        
        # Filter by user if not admin
        if not current_user.is_admin:
            team_leads_query = team_leads_query.filter(
                TeamAssignment.assigned_to_user_id == current_user.id
            )
        elif filter_user_id:
            team_leads_query = team_leads_query.filter(
                TeamAssignment.assigned_to_user_id == filter_user_id
            )
        
        team_assignments = team_leads_query.all()
        team_leads_stats['total_assigned'] = len(team_assignments)
        team_leads_stats['pending'] = sum(1 for a in team_assignments if not a.added_to_crm)
        team_leads_stats['contacted'] = sum(1 for a in team_assignments if a.status == 'Contacted')
        team_leads_stats['added_to_crm'] = sum(1 for a in team_assignments if a.added_to_crm)
        
        return jsonify({
            'todays_followups': todays_followups,
            'initial_assignment': total_initial_count,
            'completion_rate': completion_rate,
            'new_leads_today': new_leads_today,
            'completed_followups': total_worked_count,
            'pending_followups': pending_followups,
            'team_leads': team_leads_stats
        })
        
    except Exception as e:
        print(f"Error in api_dashboard_metrics: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'message': 'Failed to fetch dashboard metrics'}), 500

@application.route('/api/dashboard/team-performance', methods=['GET'])
@login_required
def api_dashboard_team_performance():
    """Get team performance data for a specific date"""
    try:
        date_str = request.args.get('date', datetime.now(ist).strftime('%Y-%m-%d'))
        
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = datetime.now(ist).date()
        
        target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
        target_end = target_start + timedelta(days=1)
        target_start_utc = target_start.astimezone(pytz.UTC)
        target_end_utc = target_end.astimezone(pytz.UTC)
        
        # Get user_id filter (only for admins)
        user_id_param = request.args.get('user_id', '')
        filter_user_id = None
        if user_id_param and current_user.is_admin:
            try:
                filter_user_id = int(user_id_param)
            except ValueError:
                pass
        
        # Get users based on permissions and filter
        if filter_user_id:
            # Admin filtering by specific user
            users = User.query.filter_by(id=filter_user_id).all()
        elif current_user.is_admin:
            users = User.query.all()
        else:
            users = [current_user]
        
        team_performance = []
        
        for user in users:
            # Get initial followup count
            initial_count = get_initial_followup_count(user.id, target_date)
            
            # Get worked leads count
            worked_count = get_worked_leads_for_date(user.id, target_date)
            
            # Calculate pending
            pending_count = max(0, initial_count - worked_count)
            
            # Calculate completion rate
            completion_rate = calculate_completion_rate(initial_count, worked_count)
            
            # Get new leads count
            new_leads_count = db.session.query(db.func.count(Lead.id)).filter(
                Lead.creator_id == user.id,
                Lead.created_at >= target_start_utc,
                Lead.created_at < target_end_utc
            ).scalar() or 0
            
            team_performance.append({
                'id': user.id,
                'name': user.name,
                'assigned': initial_count,
                'worked': worked_count,
                'pending': pending_count,
                'completion_rate': completion_rate,
                'new_leads': new_leads_count
            })
        
        # Sort by assigned in descending order
        team_performance.sort(key=lambda x: x['assigned'], reverse=True)
        
        return jsonify(team_performance)
        
    except Exception as e:
        print(f"Error in api_dashboard_team_performance: {e}")
        return jsonify({'error': str(e)}), 500

@application.route('/api/followups', methods=['GET'])
@login_required
def api_followups():
    """Search and filter followups with JSON response"""
    try:
        # Get query parameters
        search = request.args.get('search', '')
        date = request.args.get('date', '')
        created_date = request.args.get('created_date', '')
        modified_date = request.args.get('modified_date', '')
        car_registration = request.args.get('car_registration', '')
        mobile = request.args.get('mobile', '')
        status = request.args.get('status', '')
        user_id = request.args.get('user_id', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Start with base query
        query = Lead.query
        
        # Apply user filter based on permissions
        if current_user.is_admin and user_id:
            try:
                query = query.filter(Lead.creator_id == int(user_id))
            except ValueError:
                pass
        elif not current_user.is_admin:
            query = query.filter(Lead.creator_id == current_user.id)
        
        # Apply date filters
        if date:
            try:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
                # Create IST datetime range for the selected date
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_end = target_start + timedelta(days=1)
                # Convert to UTC for database query
                target_start_utc = target_start.astimezone(pytz.UTC)
                target_end_utc = target_end.astimezone(pytz.UTC)
                
                # Debug logging
                print(f"API followups date filter - Selected: {date}, IST range: {target_start} to {target_end}, UTC range: {target_start_utc} to {target_end_utc}")
                
                query = query.filter(
                    Lead.followup_date >= target_start_utc,
                    Lead.followup_date < target_end_utc
                )
            except ValueError:
                pass
        
        if created_date:
            try:
                target_date = datetime.strptime(created_date, '%Y-%m-%d').date()
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_end = target_start + timedelta(days=1)
                target_start_utc = target_start.astimezone(pytz.UTC)
                target_end_utc = target_end.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.created_at >= target_start_utc,
                    Lead.created_at < target_end_utc
                )
            except ValueError:
                pass
        
        if modified_date:
            try:
                target_date = datetime.strptime(modified_date, '%Y-%m-%d').date()
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_end = target_start + timedelta(days=1)
                target_start_utc = target_start.astimezone(pytz.UTC)
                target_end_utc = target_end.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.modified_at >= target_start_utc,
                    Lead.modified_at < target_end_utc
                )
            except ValueError:
                pass
        
        # Apply other filters
        if car_registration:
            query = query.filter(Lead.car_registration.ilike(f'%{car_registration}%'))
        
        if mobile:
            query = query.filter(Lead.mobile.ilike(f'%{mobile}%'))
        
        if status:
            query = query.filter(Lead.status == status)
        
        if search:
            query = query.filter(
                db.or_(
                    Lead.customer_name.ilike(f'%{search}%'),
                    Lead.mobile.ilike(f'%{search}%'),
                    Lead.car_registration.ilike(f'%{search}%'),
                    Lead.car_model.ilike(f'%{search}%'),
                    Lead.remarks.ilike(f'%{search}%')
                )
            )
        
        # Status priority order: New Lead > Feedback > Confirmed > Open > Completed > Needs Followup > Did Not Pick Up > Dead Lead
        status_order = db.case(
            (Lead.status == 'New Lead', 0),
            (Lead.status == 'Feedback', 1),
            (Lead.status == 'Confirmed', 2),
            (Lead.status == 'Open', 3),
            (Lead.status == 'Completed', 4),
            (Lead.status == 'Needs Followup', 5),
            (Lead.status == 'Did Not Pick Up', 6),
            (Lead.status == 'Dead Lead', 7),
            else_=8
        )
        
        # Paginate - order by status priority first, then by followup_date ascending (earliest first)
        pagination = query.order_by(status_order.asc(), Lead.followup_date.asc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Convert to JSON
        leads = []
        for lead in pagination.items:
            creator_name = lead.creator.name if lead.creator else 'Unknown'
            
            # Ensure followup_date is timezone-aware before converting to ISO
            followup_date_iso = None
            if lead.followup_date:
                # If naive, assume it's UTC and localize it
                if lead.followup_date.tzinfo is None:
                    followup_date_aware = pytz.UTC.localize(lead.followup_date)
                else:
                    followup_date_aware = lead.followup_date
                followup_date_iso = followup_date_aware.isoformat()
            
            leads.append({
                'id': lead.id,
                'customer_name': lead.customer_name,
                'mobile': lead.mobile,
                'car_registration': lead.car_registration or '',
                'car_model': lead.car_model or '',
                'followup_date': followup_date_iso,
                'status': lead.status,
                'remarks': lead.remarks or '',
                'creator_id': lead.creator_id,
                'creator_name': creator_name,
                'created_at': lead.created_at.isoformat() if lead.created_at else None,
                'modified_at': lead.modified_at.isoformat() if lead.modified_at else None
            })
        
        return jsonify({
            'leads': leads,
            'total_pages': pagination.pages,
            'current_page': page,
            'per_page': per_page,
            'total': pagination.total
        })
        
    except Exception as e:
        print(f"Error in api_followups: {e}")
        return jsonify({'error': str(e)}), 500

@application.route('/api/followups/<int:lead_id>', methods=['GET'])
@login_required
def api_get_followup(lead_id):
    """Get a single followup/lead by ID"""
    try:
        lead = Lead.query.get_or_404(lead_id)
        
        # Check permissions
        if not current_user.is_admin and lead.creator_id != current_user.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        creator_name = lead.creator.name if lead.creator else 'Unknown'
        
        # Ensure followup_date is timezone-aware before converting to ISO
        followup_date_iso = None
        if lead.followup_date:
            # If naive, assume it's UTC and localize it
            if lead.followup_date.tzinfo is None:
                followup_date_aware = pytz.UTC.localize(lead.followup_date)
            else:
                followup_date_aware = lead.followup_date
            followup_date_iso = followup_date_aware.isoformat()
        
        lead_data = {
            'id': lead.id,
            'customer_name': lead.customer_name,
            'mobile': lead.mobile,
            'car_registration': lead.car_registration or '',
            'car_model': lead.car_model or '',
            'followup_date': followup_date_iso,
            'status': lead.status,
            'remarks': lead.remarks or '',
            'creator_id': lead.creator_id,
            'creator_name': creator_name,
            'created_at': lead.created_at.isoformat() if lead.created_at else None,
            'modified_at': lead.modified_at.isoformat() if lead.modified_at else None
        }
        
        return jsonify({
            'success': True,
            'lead': lead_data
        })
        
    except Exception as e:
        print(f"Error fetching followup: {e}")
        return jsonify({'success': False, 'message': 'Error fetching followup'}), 500

@application.route('/api/followups/<int:lead_id>', methods=['PATCH'])
@login_required
def api_update_followup(lead_id):
    """Update a followup/lead"""
    try:
        lead = Lead.query.get_or_404(lead_id)
        
        # Check permissions
        if not current_user.is_admin and lead.creator_id != current_user.id:
            return jsonify({'error': 'Permission denied'}), 403
        
        data = request.get_json()
        
        # Update fields
        if 'customer_name' in data:
            lead.customer_name = data['customer_name']
        if 'mobile' in data:
            normalized_mobile = normalize_mobile_number(data['mobile'])
            if not normalized_mobile:
                return jsonify({'error': 'Invalid mobile number format. Please use: +917404625111, 7404625111, or 917404625111'}), 400
            lead.mobile = normalized_mobile
        if 'car_registration' in data:
            lead.car_registration = data['car_registration']
        if 'car_model' in data:
            lead.car_model = data['car_model'].strip() if data['car_model'] else None
        if 'status' in data:
            lead.status = data['status']
        if 'remarks' in data:
            lead.remarks = data['remarks']
        if 'followup_date' in data and data['followup_date']:
            # Parse date string - frontend now sends YYYY-MM-DD format to avoid timezone issues
            try:
                # Try parsing as YYYY-MM-DD first (preferred format)
                if isinstance(data['followup_date'], str) and len(data['followup_date']) == 10 and data['followup_date'].count('-') == 2:
                    followup_date_only = datetime.strptime(data['followup_date'], '%Y-%m-%d').date()
                else:
                    # Fallback: try parsing ISO format
                    followup_dt = datetime.fromisoformat(data['followup_date'].replace('Z', '+00:00'))
                    followup_date_only = followup_dt.date()
                
                # Create datetime at midnight IST for the selected date, then convert to UTC
                followup_start = ist.localize(datetime.combine(followup_date_only, datetime.min.time()))
                new_followup_date = followup_start.astimezone(pytz.UTC)
                
                # Always update to ensure the date is exactly as the user selected
                lead.followup_date = new_followup_date
            except (ValueError, AttributeError) as e:
                print(f"Error parsing followup_date: {e}")
                # If parsing fails, don't update the date to avoid breaking existing data
                pass
        
        lead.modified_at = datetime.now(ist)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Lead updated successfully',
            'lead': {
                'id': lead.id,
                'customer_name': lead.customer_name,
                'mobile': lead.mobile,
                'car_registration': lead.car_registration,
                'followup_date': lead.followup_date.isoformat() if lead.followup_date else None,
                'status': lead.status,
                'remarks': lead.remarks,
                'modified_at': lead.modified_at.isoformat() if lead.modified_at else None,
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating followup: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'message': 'Error updating lead'}), 500

@application.route('/api/followups/<int:lead_id>', methods=['DELETE'])
@login_required
def api_delete_followup(lead_id):
    """Delete a followup/lead"""
    try:
        lead = Lead.query.get_or_404(lead_id)
        
        # Check permissions - only admin can delete
        if not current_user.is_admin:
            return jsonify({'error': 'Permission denied. Only admins can delete leads.'}), 403
        
        # Delete the lead
        db.session.delete(lead)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Lead deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting followup: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'message': 'Error deleting lead'}), 500

@application.route('/api/user/current', methods=['GET', 'OPTIONS'])
def api_user_current():
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = make_response()
        origin = request.headers.get('Origin', 'http://gaadimech-crm-unified.eba-ftgmu9fp.ap-south-1.elasticbeanstalk.com')
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept, X-Requested-With, Origin')
        return response
    
    # Debug logging
    print(f"[DEBUG] /api/user/current called from origin: {request.headers.get('Origin')}")
    print(f"[DEBUG] Request method: {request.method}")
    print(f"[DEBUG] Has session cookie: {request.cookies.get('session') is not None}")
    
    """Get current user info for admin check"""
    try:
        # Check if user is authenticated without redirecting
        # Handle case where database connection might fail
        try:
            if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
                return jsonify({'error': 'Not authenticated'}), 401
            
            return jsonify({
                'id': current_user.id,
                'username': current_user.username,
                'name': current_user.name,
                'is_admin': current_user.is_admin
            })
        except Exception as db_error:
            # If database connection fails, return 503 (Service Unavailable) instead of 401
            # This prevents redirect loops when DB is down
            print(f"Database error in api_user_current: {db_error}")
            return jsonify({'error': 'Database connection failed', 'message': 'Service temporarily unavailable'}), 503
    except Exception as e:
        print(f"Error in api_user_current: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# WhatsApp Template API endpoints
@application.route('/api/whatsapp-templates', methods=['GET', 'OPTIONS'])
@login_required
def api_whatsapp_templates():
    """Get all WhatsApp templates"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    try:
        templates = WhatsAppTemplate.query.order_by(WhatsAppTemplate.created_at.desc()).all()
        response = jsonify({
            'templates': [{
                'id': t.id,
                'name': t.name,
                'message': t.message,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'updated_at': t.updated_at.isoformat() if t.updated_at else None,
                'created_by': t.created_by
            } for t in templates]
        })
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    except Exception as e:
        print(f"Error fetching WhatsApp templates: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@application.route('/api/whatsapp-templates', methods=['POST', 'OPTIONS'])
@login_required
def api_create_whatsapp_template():
    """Create a new WhatsApp template"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    try:
        data = request.get_json()
        if not data or not data.get('name') or not data.get('message'):
            return jsonify({'error': 'Name and message are required'}), 400
        
        template = WhatsAppTemplate(
            name=data['name'],
            message=data['message'],
            created_by=current_user.id
        )
        db.session.add(template)
        db.session.commit()
        
        response = jsonify({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'message': template.message,
                'created_at': template.created_at.isoformat() if template.created_at else None,
                'updated_at': template.updated_at.isoformat() if template.updated_at else None,
                'created_by': template.created_by
            }
        })
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 201
    except Exception as e:
        db.session.rollback()
        print(f"Error creating WhatsApp template: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@application.route('/api/whatsapp-templates/<int:template_id>', methods=['PUT', 'OPTIONS'])
@login_required
def api_update_whatsapp_template(template_id):
    """Update an existing WhatsApp template"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    try:
        template = WhatsAppTemplate.query.get_or_404(template_id)
        
        # Check permissions - only creator or admin can edit
        if template.created_by != current_user.id and not current_user.is_admin:
            return jsonify({'error': 'Permission denied'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        if 'name' in data:
            template.name = data['name']
        if 'message' in data:
            template.message = data['message']
        
        template.updated_at = datetime.now(ist)
        db.session.commit()
        
        response = jsonify({
            'success': True,
            'template': {
                'id': template.id,
                'name': template.name,
                'message': template.message,
                'created_at': template.created_at.isoformat() if template.created_at else None,
                'updated_at': template.updated_at.isoformat() if template.updated_at else None,
                'created_by': template.created_by
            }
        })
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    except Exception as e:
        db.session.rollback()
        print(f"Error updating WhatsApp template: {e}")
        return jsonify({'error': str(e)}), 500

@application.route('/api/whatsapp-templates/<int:template_id>', methods=['DELETE', 'OPTIONS'])
@login_required
def api_delete_whatsapp_template(template_id):
    """Delete a WhatsApp template"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    try:
        template = WhatsAppTemplate.query.get_or_404(template_id)
        
        # Check permissions - only creator or admin can delete
        if template.created_by != current_user.id and not current_user.is_admin:
            return jsonify({'error': 'Permission denied'}), 403
        
        db.session.delete(template)
        db.session.commit()
        
        response = jsonify({'success': True, 'message': 'Template deleted successfully'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting WhatsApp template: {e}")
        return jsonify({'error': str(e)}), 500

@application.route('/followups')
def followups():
    # Only serve Flask template for API requests, otherwise serve Next.js
    is_api_request = request.headers.get('Accept', '').startswith('application/json')
    if is_api_request and not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    # For page requests, serve Next.js frontend
    return serve_frontend()

@application.route('/followups-old')
@login_required
def followups_old():
    try:
        # Get query parameters with better defaults
        selected_date = request.args.get('date', '')  # Empty means show all
        selected_user_id = request.args.get('user_id', '')
        created_date = request.args.get('created_date', '')
        modified_date = request.args.get('modified_date', '')
        car_registration = request.args.get('car_registration', '')
        mobile = request.args.get('mobile', '')
        status = request.args.get('status', '')
        search = request.args.get('search', '')
        
        # Start with base query
        query = Lead.query
        
        # Apply user filter based on permissions
        if current_user.is_admin and selected_user_id:
            try:
                user_id = int(selected_user_id)
                query = query.filter(Lead.creator_id == user_id)
            except ValueError:
                pass  # Invalid user ID, show all
        elif not current_user.is_admin:
            # Non-admin users can only see their own leads
            query = query.filter(Lead.creator_id == current_user.id)
        
        # Apply date filters
        if selected_date:
            try:
                target_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_end = target_start + timedelta(days=1)
                target_start_utc = target_start.astimezone(pytz.UTC)
                target_end_utc = target_end.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.followup_date >= target_start_utc,
                    Lead.followup_date < target_end_utc
                )
            except ValueError:
                pass
        
        if created_date:
            try:
                target_date = datetime.strptime(created_date, '%Y-%m-%d').date()
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_end = target_start + timedelta(days=1)
                target_start_utc = target_start.astimezone(pytz.UTC)
                target_end_utc = target_end.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.created_at >= target_start_utc,
                    Lead.created_at < target_end_utc
                )
            except ValueError:
                pass
        
        if modified_date:
            try:
                target_date = datetime.strptime(modified_date, '%Y-%m-%d').date()
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_end = target_start + timedelta(days=1)
                target_start_utc = target_start.astimezone(pytz.UTC)
                target_end_utc = target_end.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.modified_at >= target_start_utc,
                    Lead.modified_at < target_end_utc
                )
            except ValueError:
                pass
        
        # Apply other filters
        if car_registration:
            query = query.filter(Lead.car_registration.ilike(f'%{car_registration}%'))
        
        if mobile:
            query = query.filter(Lead.mobile.ilike(f'%{mobile}%'))
        
        if status:
            query = query.filter(Lead.status == status)
        
        if search:
            query = query.filter(
                db.or_(
                    Lead.customer_name.ilike(f'%{search}%'),
                    Lead.mobile.ilike(f'%{search}%'),
                    Lead.car_registration.ilike(f'%{search}%'),
                    Lead.remarks.ilike(f'%{search}%')
                )
            )
        
        # Get all users for the dropdown
        users = User.query.all() if current_user.is_admin else [current_user]
        
        # Get the followups with pagination
        page = request.args.get('page', 1, type=int)
        per_page = 100  # Show more results per page to see more leads
        
        followups_pagination = query.order_by(Lead.followup_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Convert followups to IST for display
        for followup in followups_pagination.items:
            if followup.followup_date:
                followup.followup_date = utc_to_ist(followup.followup_date)
            if followup.created_at:
                followup.created_at = utc_to_ist(followup.created_at)
            if followup.modified_at:
                followup.modified_at = utc_to_ist(followup.modified_at)
        
        return render_template('followups.html',
            followups=followups_pagination.items,
            followups_pagination=followups_pagination,
            users=users,
            selected_date=selected_date,
            selected_user_id=selected_user_id,
            created_date=created_date,
            modified_date=modified_date,
            car_registration=car_registration,
            mobile=mobile,
            status=status,
            search=search,
            USER_MOBILE_MAPPING=USER_MOBILE_MAPPING
        )
        
    except Exception as e:
        print(f"Followups error: {str(e)}")
        flash('Error loading followups. Please try again.', 'error')
        return redirect(url_for('index'))

# Admin API endpoints for new TypeScript frontend

@application.route('/api/admin/unassigned-leads/<int:lead_id>', methods=['DELETE'])
@login_required
def api_delete_unassigned_lead(lead_id):
    """Delete an unassigned lead and all its assignments"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get the unassigned lead
        lead = UnassignedLead.query.get_or_404(lead_id)
        
        # Delete all team assignments for this lead first (cascade)
        TeamAssignment.query.filter_by(unassigned_lead_id=lead_id).delete()
        
        # Delete the lead
        db.session.delete(lead)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Lead and all assignments deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting unassigned lead: {str(e)}")
        return jsonify({'error': f'Error deleting lead: {str(e)}'}), 500

@application.route('/api/admin/unassigned-leads', methods=['GET'])
@login_required
def api_admin_unassigned_leads():
    """Get unassigned leads for admin"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        search = request.args.get('search', '')
        created_date = request.args.get('created_date', '')
        
        query = UnassignedLead.query
        
        # Apply search filter
        if search:
            query = query.filter(
                db.or_(
                    UnassignedLead.customer_name.ilike(f'%{search}%'),
                    UnassignedLead.mobile.ilike(f'%{search}%'),
                    UnassignedLead.car_manufacturer.ilike(f'%{search}%'),
                    UnassignedLead.car_model.ilike(f'%{search}%')
                )
            )
        
        # Apply date filter
        if created_date:
            try:
                filter_date = datetime.strptime(created_date, '%Y-%m-%d').date()
                start_date = ist.localize(datetime.combine(filter_date, datetime.min.time()))
                end_date = start_date + timedelta(days=1)
                start_date_utc = start_date.astimezone(pytz.UTC)
                end_date_utc = end_date.astimezone(pytz.UTC)
                
                query = query.filter(
                    UnassignedLead.created_at >= start_date_utc,
                    UnassignedLead.created_at < end_date_utc
                )
            except ValueError:
                pass
        
        # Get recent leads
        unassigned_leads = query.order_by(UnassignedLead.created_at.desc()).limit(100).all()
        
        # Convert to JSON and collect assignment info
        leads = []
        for lead in unassigned_leads:
            # Get current assignment if any
            current_assignment = TeamAssignment.query.filter_by(
                unassigned_lead_id=lead.id
            ).order_by(TeamAssignment.assigned_at.desc()).first()
            
            assigned_to = None
            added_to_crm = False
            assigned_date = None
            assignment_id = None
            if current_assignment:
                assigned_user = User.query.get(current_assignment.assigned_to_user_id)
                assigned_to = assigned_user.name if assigned_user else None
                added_to_crm = current_assignment.added_to_crm or False
                assignment_id = current_assignment.id
                # Format assigned_date in IST
                if current_assignment.assigned_date:
                    assigned_date = current_assignment.assigned_date.strftime('%Y-%m-%d')
            
            # Combine manufacturer and model for display
            combined_car_model = None
            if lead.car_manufacturer and lead.car_model:
                combined_car_model = f"{lead.car_manufacturer} {lead.car_model}"
            elif lead.car_manufacturer:
                combined_car_model = lead.car_manufacturer
            elif lead.car_model:
                combined_car_model = lead.car_model
            
            # Format scheduled_date in IST
            scheduled_date_str = None
            if lead.scheduled_date:
                scheduled_date = lead.scheduled_date
                if scheduled_date.tzinfo is not None:
                    scheduled_date_ist = scheduled_date.astimezone(ist)
                else:
                    scheduled_date_ist = ist.localize(scheduled_date)
                scheduled_date_str = scheduled_date_ist.strftime('%Y-%m-%d')
            
            leads.append({
                'id': lead.id,
                'mobile': lead.mobile,
                'customer_name': lead.customer_name or '',
                'car_model': combined_car_model or '',  # Combined manufacturer and model
                'pickup_type': lead.pickup_type or '',
                'service_type': lead.service_type or '',
                'scheduled_date': scheduled_date_str,
                'source': lead.source or '',
                'remarks': lead.remarks or '',
                'created_at': lead.created_at.isoformat() if lead.created_at else None,
                'assigned_to': assigned_to,
                'added_to_crm': added_to_crm,  # Track if lead has been added to CRM
                'assigned_date': assigned_date,
                'assignment_id': assignment_id
            })
        
        # Sort leads: pending (not added_to_crm) first, then added_to_crm, then no assignment
        # Within each group, sort by created_at desc (most recent first)
        leads.sort(key=lambda x: (
            0 if x.get('added_to_crm') is False else (1 if x.get('added_to_crm') is True else 2),
            -1 if x.get('created_at') else 0  # Most recent first (negative for desc)
        ))
        # Reverse the created_at comparison since we want desc
        leads.sort(key=lambda x: (
            0 if x.get('added_to_crm') is False else (1 if x.get('added_to_crm') is True else 2)
        ))
        # Then sort by created_at desc within each group
        pending_leads = [l for l in leads if l.get('added_to_crm') is False]
        added_leads = [l for l in leads if l.get('added_to_crm') is True]
        unassigned_leads_list = [l for l in leads if l.get('added_to_crm') is None or l.get('added_to_crm') is not False and l.get('added_to_crm') is not True]
        
        # Sort each group by created_at desc
        pending_leads.sort(key=lambda x: x.get('created_at') or '', reverse=True)
        added_leads.sort(key=lambda x: x.get('created_at') or '', reverse=True)
        unassigned_leads_list.sort(key=lambda x: x.get('created_at') or '', reverse=True)
        
        # Combine: pending first, then added, then unassigned
        leads = pending_leads + added_leads + unassigned_leads_list
        
        return jsonify({'leads': leads})
        
    except Exception as e:
        print(f"Error in api_admin_unassigned_leads: {e}")
        return jsonify({'error': str(e)}), 500

@application.route('/api/admin/unassigned-leads/<int:lead_id>/details', methods=['GET'])
@login_required
def api_admin_unassigned_lead_details(lead_id):
    """Get detailed information about an unassigned lead including CRM details if added"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        # Get the unassigned lead
        lead = UnassignedLead.query.get_or_404(lead_id)
        
        # Get current assignment
        current_assignment = TeamAssignment.query.filter_by(
            unassigned_lead_id=lead.id
        ).order_by(TeamAssignment.assigned_at.desc()).first()
        
        # Format scheduled_date in IST
        scheduled_date_str = None
        if lead.scheduled_date:
            scheduled_date = lead.scheduled_date
            if scheduled_date.tzinfo is not None:
                scheduled_date_ist = scheduled_date.astimezone(ist)
            else:
                scheduled_date_ist = ist.localize(scheduled_date)
            scheduled_date_str = scheduled_date_ist.strftime('%Y-%m-%d')
        
        # Get CRM lead details if added to CRM
        crm_lead = None
        if current_assignment and current_assignment.added_to_crm:
            # Find the CRM lead created from this assignment
            # We can match by mobile number and creator (the assigned user)
            crm_leads = Lead.query.filter_by(
                mobile=lead.mobile,
                creator_id=current_assignment.assigned_to_user_id
            ).order_by(Lead.created_at.desc()).all()
            
            # Find the most recent one that was likely created from this assignment
            # (created around the same time as processed_at)
            if crm_leads:
                # Get the one closest to processed_at time
                if current_assignment.processed_at:
                    closest_lead = min(crm_leads, key=lambda l: abs(
                        (l.created_at.replace(tzinfo=pytz.UTC) if l.created_at.tzinfo is None else l.created_at) - 
                        (current_assignment.processed_at.replace(tzinfo=pytz.UTC) if current_assignment.processed_at.tzinfo is None else current_assignment.processed_at)
                    ))
                else:
                    closest_lead = crm_leads[0]
                
                # Format followup_date in IST
                followup_date_str = None
                if closest_lead.followup_date:
                    followup_date = closest_lead.followup_date
                    if followup_date.tzinfo is not None:
                        followup_date_ist = followup_date.astimezone(ist)
                    else:
                        followup_date_ist = pytz.UTC.localize(followup_date).astimezone(ist)
                    followup_date_str = followup_date_ist.strftime('%Y-%m-%d')
                
                crm_lead = {
                    'id': closest_lead.id,
                    'status': closest_lead.status,
                    'car_registration': closest_lead.car_registration or '',
                    'followup_date': followup_date_str,
                    'remarks': closest_lead.remarks or '',
                    'created_at': closest_lead.created_at.isoformat() if closest_lead.created_at else None,
                    'modified_at': closest_lead.modified_at.isoformat() if closest_lead.modified_at else None
                }
        
        # Format assigned_date in IST
        assigned_date_str = None
        if current_assignment and current_assignment.assigned_date:
            assigned_date_str = current_assignment.assigned_date.strftime('%Y-%m-%d')
        
        return jsonify({
            'lead': {
                'id': lead.id,
                'mobile': lead.mobile,
                'customer_name': lead.customer_name or '',
                'car_model': f"{lead.car_manufacturer} {lead.car_model}".strip() if lead.car_manufacturer or lead.car_model else '',
                'pickup_type': lead.pickup_type or '',
                'service_type': lead.service_type or '',
                'scheduled_date': scheduled_date_str,
                'source': lead.source or '',
                'remarks': lead.remarks or '',
                'created_at': lead.created_at.isoformat() if lead.created_at else None,
            },
            'assignment': {
                'assigned_to': User.query.get(current_assignment.assigned_to_user_id).name if current_assignment else None,
                'assigned_date': assigned_date_str,
                'added_to_crm': current_assignment.added_to_crm if current_assignment else False,
                'status': current_assignment.status if current_assignment else None,
            },
            'crm_lead': crm_lead
        })
        
    except Exception as e:
        print(f"Error in api_admin_unassigned_lead_details: {e}")
        return jsonify({'error': str(e)}), 500

@application.route('/api/admin/team-members', methods=['GET'])
@login_required
def api_admin_team_members():
    """Get list of team members (non-admin users)"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        # Get all non-admin users
        team_members = User.query.filter_by(is_admin=False).all()
        
        members = [{
            'id': member.id,
            'name': member.name,
            'username': member.username
        } for member in team_members]
        
        return jsonify({'members': members})
        
    except Exception as e:
        print(f"Error in api_admin_team_members: {e}")
        return jsonify({'error': str(e)}), 500

@application.route('/api/admin/download-leads/count', methods=['GET'])
@login_required
def api_admin_download_leads_count():
    """Get count of leads matching filter criteria"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        # Get query parameters
        filter_type = request.args.get('filter_type', 'followup_date')  # 'created_date', 'followup_date', or 'date_range'
        date = request.args.get('date', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        user_ids = request.args.getlist('user_ids')  # Can be multiple user IDs
        
        # Build base query
        query = Lead.query
        
        # Apply date filters
        if filter_type == 'created_date' and date:
            try:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_end = target_start + timedelta(days=1)
                target_start_utc = target_start.astimezone(pytz.UTC)
                target_end_utc = target_end.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.created_at >= target_start_utc,
                    Lead.created_at < target_end_utc
                )
            except ValueError:
                pass
        elif filter_type == 'followup_date' and date:
            try:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_end = target_start + timedelta(days=1)
                target_start_utc = target_start.astimezone(pytz.UTC)
                target_end_utc = target_end.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.followup_date >= target_start_utc,
                    Lead.followup_date < target_end_utc
                )
            except ValueError:
                pass
        elif filter_type == 'date_range' and start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                # For date range, we'll filter by followup_date by default
                # But we can make it configurable if needed
                start_ist = ist.localize(datetime.combine(start, datetime.min.time()))
                end_ist = ist.localize(datetime.combine(end, datetime.min.time())) + timedelta(days=1)
                start_utc = start_ist.astimezone(pytz.UTC)
                end_utc = end_ist.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.followup_date >= start_utc,
                    Lead.followup_date < end_utc
                )
            except ValueError:
                pass
        
        # Apply user filter
        if user_ids:
            try:
                user_id_list = [int(uid) for uid in user_ids if uid]
                if user_id_list:
                    query = query.filter(Lead.creator_id.in_(user_id_list))
            except ValueError:
                pass
        
        # Get count
        count = query.count()
        
        return jsonify({
            'success': True,
            'count': count
        })
        
    except Exception as e:
        print(f"Error in api_admin_download_leads_count: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@application.route('/api/admin/download-leads/export', methods=['GET'])
@login_required
def api_admin_download_leads_export():
    """Export leads as CSV with phone_number header"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        # Get query parameters
        filter_type = request.args.get('filter_type', 'followup_date')  # 'created_date', 'followup_date', or 'date_range'
        date = request.args.get('date', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        user_ids = request.args.getlist('user_ids')  # Can be multiple user IDs
        
        # Build base query
        query = Lead.query
        
        # Apply date filters
        if filter_type == 'created_date' and date:
            try:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_end = target_start + timedelta(days=1)
                target_start_utc = target_start.astimezone(pytz.UTC)
                target_end_utc = target_end.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.created_at >= target_start_utc,
                    Lead.created_at < target_end_utc
                )
            except ValueError:
                pass
        elif filter_type == 'followup_date' and date:
            try:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_end = target_start + timedelta(days=1)
                target_start_utc = target_start.astimezone(pytz.UTC)
                target_end_utc = target_end.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.followup_date >= target_start_utc,
                    Lead.followup_date < target_end_utc
                )
            except ValueError:
                pass
        elif filter_type == 'date_range' and start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                # For date range, we'll filter by followup_date by default
                start_ist = ist.localize(datetime.combine(start, datetime.min.time()))
                end_ist = ist.localize(datetime.combine(end, datetime.min.time())) + timedelta(days=1)
                start_utc = start_ist.astimezone(pytz.UTC)
                end_utc = end_ist.astimezone(pytz.UTC)
                query = query.filter(
                    Lead.followup_date >= start_utc,
                    Lead.followup_date < end_utc
                )
            except ValueError:
                pass
        
        # Apply user filter
        if user_ids:
            try:
                user_id_list = [int(uid) for uid in user_ids if uid]
                if user_id_list:
                    query = query.filter(Lead.creator_id.in_(user_id_list))
            except ValueError:
                pass
        
        # Get leads
        leads = query.order_by(Lead.created_at.desc()).all()
        
        # Prepare CSV data with phone_number header
        csv_header = 'phone_number\n'
        csv_data = csv_header
        
        # Extract unique phone numbers (in case of duplicates)
        phone_numbers = set()
        for lead in leads:
            if lead.mobile:
                phone_numbers.add(lead.mobile)
        
        # Add phone numbers to CSV
        for phone in sorted(phone_numbers):
            csv_data += f"{phone}\n"
        
        # Generate filename based on filter type
        if filter_type == 'followup_date' and date:
            filename = f"FD-{date}.csv"
        elif filter_type == 'created_date' and date:
            filename = f"CD-{date}.csv"
        elif filter_type == 'date_range' and start_date and end_date:
            filename = f"DR-{start_date}_to_{end_date}.csv"
        else:
            filename = "leads.csv"
        
        # Return response
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        print(f"Error in api_admin_download_leads_export: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'message': 'Failed to export leads'}), 500

@application.route('/api/admin/users', methods=['GET', 'POST'])
@login_required
def get_all_users():
    """Get all users or create a new user (admin only)"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    if request.method == 'POST':
        # Create new user
        try:
            data = request.get_json()
            username = data.get('username')
            name = data.get('name')
            password = data.get('password')
            is_admin = data.get('is_admin', False)
            
            # Validation
            if not username or not name or not password:
                return jsonify({'error': 'Username, name, and password are required'}), 400
            
            if len(password) < 6:
                return jsonify({'error': 'Password must be at least 6 characters long'}), 400
            
            # Check if username already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                return jsonify({'error': 'Username already exists'}), 400
            
            # Create new user
            new_user = User(
                username=username,
                name=name,
                is_admin=bool(is_admin)
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'User {username} created successfully',
                'user': {
                    'id': new_user.id,
                    'username': new_user.username,
                    'name': new_user.name,
                    'is_admin': new_user.is_admin
                }
            }), 201
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating user: {e}")
            return jsonify({'error': 'Failed to create user'}), 500
    
    # GET request - return all users
    try:
        # Get all users
        all_users = User.query.order_by(User.id.asc()).all()
        
        users = [{
            'id': user.id,
            'username': user.username,
            'name': user.name,
            'is_admin': user.is_admin
        } for user in all_users]
        
        return jsonify({'users': users})
        
    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({'error': 'Failed to fetch users'}), 500

@application.route('/api/admin/users/<int:user_id>/password', methods=['PATCH'])
@login_required
def update_user_password(user_id):
    """Update a user's password (admin only, no old password required)"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        data = request.get_json()
        new_password = data.get('new_password')
        
        if not new_password:
            return jsonify({'error': 'New password is required'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters long'}), 400
        
        # Get the user
        user = User.query.get_or_404(user_id)
        
        # Update password using set_password method (hashes it automatically)
        user.set_password(new_password)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Password updated successfully for user {user.username}'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating password: {e}")
        return jsonify({'error': 'Failed to update password'}), 500

@application.route('/api/admin/leads-manipulation/search', methods=['GET'])
@login_required
def api_admin_leads_manipulation_search():
    """Search and filter leads for manipulation (admin only)"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        # Get query parameters
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        user_id = request.args.get('user_id', '')
        status = request.args.get('status', '')
        search = request.args.get('search', '')
        
        # Start with base query
        query = Lead.query
        
        # Apply date range filter
        if date_from:
            try:
                target_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                target_start = ist.localize(datetime.combine(target_date, datetime.min.time()))
                target_start_utc = target_start.astimezone(pytz.UTC)
                query = query.filter(Lead.followup_date >= target_start_utc)
            except ValueError:
                pass
        
        if date_to:
            try:
                target_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                target_end = ist.localize(datetime.combine(target_date, datetime.max.time()))
                target_end_utc = target_end.astimezone(pytz.UTC)
                query = query.filter(Lead.followup_date <= target_end_utc)
            except ValueError:
                pass
        
        # Apply user filter
        if user_id:
            try:
                query = query.filter(Lead.creator_id == int(user_id))
            except ValueError:
                pass
        
        # Apply status filter
        if status:
            query = query.filter(Lead.status == status)
        
        # Apply search filter
        if search:
            query = query.filter(
                db.or_(
                    Lead.customer_name.ilike(f'%{search}%'),
                    Lead.mobile.ilike(f'%{search}%'),
                    Lead.car_registration.ilike(f'%{search}%'),
                    Lead.car_model.ilike(f'%{search}%'),
                    Lead.remarks.ilike(f'%{search}%')
                )
            )
        
        # Order by followup_date ascending - no limit for admin operations
        # Use yield_per for better memory efficiency with large datasets
        leads_list = query.order_by(Lead.followup_date.asc())
        
        # Get total count first for reporting
        total_count = leads_list.count()
        print(f"Total leads found: {total_count}")
        
        # Convert to JSON - process in batches to avoid memory issues
        leads = []
        batch_size = 1000
        offset = 0
        
        while True:
            batch = leads_list.offset(offset).limit(batch_size).all()
            if not batch:
                break
            
            for lead in batch:
                creator_name = lead.creator.name if lead.creator else 'Unknown'
                
                # Ensure followup_date is timezone-aware
                followup_date_iso = None
                if lead.followup_date:
                    if lead.followup_date.tzinfo is None:
                        followup_date_aware = pytz.UTC.localize(lead.followup_date)
                    else:
                        followup_date_aware = lead.followup_date
                    followup_date_iso = followup_date_aware.isoformat()
                
                leads.append({
                    'id': lead.id,
                    'customer_name': lead.customer_name,
                    'mobile': lead.mobile,
                    'car_registration': lead.car_registration or '',
                    'car_model': lead.car_model or '',
                    'followup_date': followup_date_iso,
                    'status': lead.status,
                    'remarks': lead.remarks or '',
                    'creator_id': lead.creator_id,
                    'creator_name': creator_name,
                    'created_at': lead.created_at.isoformat() if lead.created_at else None,
                    'modified_at': lead.modified_at.isoformat() if lead.modified_at else None
                })
            
            offset += batch_size
            print(f"Processed {len(leads)} leads so far...")
            
            # Safety check to prevent infinite loops
            if len(leads) >= total_count:
                break
        
        print(f"Total leads returned: {len(leads)}")
        
        return jsonify({'leads': leads, 'total': len(leads)})
        
    except Exception as e:
        print(f"Error in api_admin_leads_manipulation_search: {e}")
        return jsonify({'error': str(e)}), 500

@application.route('/api/admin/leads-manipulation/bulk-update', methods=['POST'])
@login_required
def api_admin_leads_manipulation_bulk_update():
    """Bulk update leads: change date, transfer user, or both (admin only)"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        data = request.get_json()
        lead_ids = data.get('lead_ids', [])
        operation_type = data.get('operation_type', 'date')  # 'date', 'user', or 'both'
        new_followup_date = data.get('new_followup_date', '')
        from_user_id = data.get('from_user_id')
        to_user_id = data.get('to_user_id')
        
        if not lead_ids or len(lead_ids) == 0:
            return jsonify({'error': 'No leads selected'}), 400
        
        # Validate operation type
        if operation_type not in ['date', 'user', 'both', 'distributed']:
            return jsonify({'error': 'Invalid operation type'}), 400
        
        # Validate date if needed
        new_followup_datetime = None
        if operation_type in ['date', 'both']:
            if not new_followup_date:
                return jsonify({'error': 'New follow-up date is required'}), 400
            try:
                # Parse date string (YYYY-MM-DD format)
                target_date = datetime.strptime(new_followup_date, '%Y-%m-%d').date()
                # Create datetime at midnight IST for the selected date, then convert to UTC
                target_datetime_ist = ist.localize(datetime.combine(target_date, datetime.min.time()))
                new_followup_datetime = target_datetime_ist.astimezone(pytz.UTC)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Validate user IDs if needed
        if operation_type in ['user', 'both']:
            if not from_user_id or not to_user_id:
                return jsonify({'error': 'Both from_user_id and to_user_id are required'}), 400
            try:
                from_user_id = int(from_user_id)
                to_user_id = int(to_user_id)
                if from_user_id == to_user_id:
                    return jsonify({'error': 'From user and to user cannot be the same'}), 400
                # Verify users exist
                from_user = User.query.get(from_user_id)
                to_user = User.query.get(to_user_id)
                if not from_user or not to_user:
                    return jsonify({'error': 'Invalid user ID(s)'}), 400
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid user ID format'}), 400
        
        # Handle distributed operation separately
        if operation_type == 'distributed':
            dist_start_date = data.get('dist_start_date', '')
            dist_end_date = data.get('dist_end_date', '')
            leads_per_day = data.get('leads_per_day')
            
            if not dist_start_date or not dist_end_date or not leads_per_day:
                return jsonify({'error': 'Distribution start date, end date, and leads per day are required'}), 400
            
            try:
                leads_per_day = int(leads_per_day)
                if leads_per_day <= 0:
                    return jsonify({'error': 'Leads per day must be a positive number'}), 400
                
                start_date = datetime.strptime(dist_start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(dist_end_date, '%Y-%m-%d').date()
                
                if start_date > end_date:
                    return jsonify({'error': 'Start date must be before or equal to end date'}), 400
                
                # Calculate number of days
                days_diff = (end_date - start_date).days + 1
                
            except ValueError:
                return jsonify({'error': 'Invalid date format or leads per day. Use YYYY-MM-DD for dates'}), 400
            
            # Get leads to update
            leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
            
            if not leads:
                return jsonify({'error': 'No leads found with provided IDs'}), 404
            
            # Filter leads by from_user_id if specified
            if from_user_id:
                try:
                    from_user_id = int(from_user_id)
                    leads = [l for l in leads if l.creator_id == from_user_id]
                except (ValueError, TypeError):
                    pass
            
            # Get target user ID (if specified, otherwise keep original)
            target_user_id = None
            if to_user_id:
                try:
                    target_user_id = int(to_user_id)
                    to_user = User.query.get(target_user_id)
                    if not to_user:
                        return jsonify({'error': 'Invalid target user ID'}), 400
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid target user ID format'}), 400
            
            # Build date list
            date_list = []
            current_date = start_date
            while current_date <= end_date:
                date_list.append(current_date)
                current_date += timedelta(days=1)
            
            # Get existing leads count per day per user
            # This helps us distribute evenly considering existing workload
            existing_counts = {}
            for date in date_list:
                date_start = ist.localize(datetime.combine(date, datetime.min.time()))
                date_end = date_start + timedelta(days=1)
                date_start_utc = date_start.astimezone(pytz.UTC)
                date_end_utc = date_end.astimezone(pytz.UTC)
                
                # Count existing leads for each user on this date
                if target_user_id:
                    # If transferring to specific user, count only that user's leads
                    count = Lead.query.filter(
                        Lead.followup_date >= date_start_utc,
                        Lead.followup_date < date_end_utc,
                        Lead.creator_id == target_user_id
                    ).count()
                    existing_counts[date] = {target_user_id: count}
                else:
                    # Count leads for all users (we'll distribute to original users)
                    user_counts = db.session.query(
                        Lead.creator_id,
                        db.func.count(Lead.id)
                    ).filter(
                        Lead.followup_date >= date_start_utc,
                        Lead.followup_date < date_end_utc
                    ).group_by(Lead.creator_id).all()
                    existing_counts[date] = {uid: cnt for uid, cnt in user_counts}
            
            # Distribute leads across dates
            updated_count = 0
            distribution_summary = {}
            lead_index = 0
            
            # Group leads by user (if not transferring to specific user)
            if not target_user_id:
                leads_by_user = {}
                for lead in leads:
                    if lead.creator_id not in leads_by_user:
                        leads_by_user[lead.creator_id] = []
                    leads_by_user[lead.creator_id].append(lead)
            else:
                # All leads go to target user
                leads_by_user = {target_user_id: leads}
            
            # Distribute leads for each user
            for user_id, user_leads in leads_by_user.items():
                user_lead_index = 0
                
                for date in date_list:
                    # Get current count for this user on this date
                    current_count = existing_counts[date].get(user_id, 0)
                    
                    # Calculate how many leads we can add to this date
                    remaining_capacity = max(0, leads_per_day - current_count)
                    
                    # Assign leads to this date
                    leads_to_assign = min(remaining_capacity, len(user_leads) - user_lead_index)
                    
                    for i in range(leads_to_assign):
                        if user_lead_index >= len(user_leads):
                            break
                        
                        lead = user_leads[user_lead_index]
                        old_followup_date = lead.followup_date
                        old_creator_id = lead.creator_id
                        
                        # Set new followup date
                        target_datetime_ist = ist.localize(datetime.combine(date, datetime.min.time()))
                        new_followup_datetime = target_datetime_ist.astimezone(pytz.UTC)
                        lead.followup_date = new_followup_datetime
                        
                        # Update user if specified
                        if target_user_id and lead.creator_id != target_user_id:
                            lead.creator_id = target_user_id
                        
                        lead.modified_at = datetime.now(ist).astimezone(pytz.UTC)
                        
                        # Record worked lead
                        record_worked_lead(lead.id, lead.creator_id, old_followup_date, new_followup_datetime)
                        
                        # Track distribution
                        date_str = date.strftime('%Y-%m-%d')
                        if date_str not in distribution_summary:
                            distribution_summary[date_str] = 0
                        distribution_summary[date_str] += 1
                        
                        updated_count += 1
                        user_lead_index += 1
                    
                    if user_lead_index >= len(user_leads):
                        break
                
                # If there are remaining leads, distribute them evenly across all dates
                if user_lead_index < len(user_leads):
                    remaining_leads = user_leads[user_lead_index:]
                    remaining_dates = date_list
                    
                    for idx, lead in enumerate(remaining_leads):
                        # Cycle through remaining dates
                        target_date = remaining_dates[idx % len(remaining_dates)]
                        old_followup_date = lead.followup_date
                        old_creator_id = lead.creator_id
                        
                        target_datetime_ist = ist.localize(datetime.combine(target_date, datetime.min.time()))
                        new_followup_datetime = target_datetime_ist.astimezone(pytz.UTC)
                        lead.followup_date = new_followup_datetime
                        
                        if target_user_id and lead.creator_id != target_user_id:
                            lead.creator_id = target_user_id
                        
                        lead.modified_at = datetime.now(ist).astimezone(pytz.UTC)
                        record_worked_lead(lead.id, lead.creator_id, old_followup_date, new_followup_datetime)
                        
                        date_str = target_date.strftime('%Y-%m-%d')
                        if date_str not in distribution_summary:
                            distribution_summary[date_str] = 0
                        distribution_summary[date_str] += 1
                        
                        updated_count += 1
            
            # Commit all changes
            db.session.commit()
            
            # Build detailed summary statistics
            summary_stats = {
                'total_leads_selected': len(lead_ids),
                'total_leads_updated': updated_count,
                'leads_not_updated': len(lead_ids) - updated_count,
                'date_range': {
                    'start': dist_start_date,
                    'end': dist_end_date,
                    'days': days_diff
                },
                'leads_per_day_limit': leads_per_day,
                'distribution_by_date': distribution_summary,
                'distribution_by_user': {}
            }
            
            # Calculate distribution by user if user transfer was involved
            if target_user_id:
                summary_stats['user_transfer'] = {
                    'from_user_id': from_user_id if from_user_id else 'All Users',
                    'to_user_id': target_user_id,
                    'to_user_name': to_user.name if to_user else 'Unknown'
                }
            
            # Calculate average leads per day
            if distribution_summary:
                total_distributed = sum(distribution_summary.values())
                summary_stats['average_leads_per_day'] = round(total_distributed / len(distribution_summary), 2)
                summary_stats['max_leads_in_day'] = max(distribution_summary.values())
                summary_stats['min_leads_in_day'] = min(distribution_summary.values())
            
            # Format distribution summary text
            summary_text = ", ".join([f"{date}: {count}" for date, count in sorted(distribution_summary.items())])
            
            return jsonify({
                'success': True,
                'message': f'Successfully distributed {updated_count} lead(s)',
                'updated_count': updated_count,
                'total_selected': len(lead_ids),
                'distribution_summary': summary_text,
                'detailed_stats': summary_stats
            })
        
        # Get leads to update (for non-distributed operations)
        leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
        
        if not leads:
            return jsonify({'error': 'No leads found with provided IDs'}), 404
        
        updated_count = 0
        
        # Perform bulk updates
        for lead in leads:
            updated = False
            old_followup_date = lead.followup_date
            old_creator_id = lead.creator_id
            
            # Update date if needed
            if operation_type in ['date', 'both']:
                lead.followup_date = new_followup_datetime
                updated = True
            
            # Update user if needed
            if operation_type in ['user', 'both']:
                # Only update if the lead is currently assigned to from_user_id
                if lead.creator_id == from_user_id:
                    lead.creator_id = to_user_id
                    updated = True
                # If operation is 'user' only and lead doesn't match from_user_id, skip it
                elif operation_type == 'user':
                    continue
            
            if updated:
                lead.modified_at = datetime.now(ist).astimezone(pytz.UTC)
                
                # Record worked lead if date changed (use new creator_id if user was changed)
                if operation_type in ['date', 'both'] and old_followup_date != new_followup_datetime:
                    record_worked_lead(lead.id, lead.creator_id, old_followup_date, new_followup_datetime)
                
                updated_count += 1
        
        # Commit all changes
        db.session.commit()
        
        # Build detailed summary statistics for non-distributed operations
        summary_stats = {
            'total_leads_selected': len(lead_ids),
            'total_leads_updated': updated_count,
            'leads_not_updated': len(lead_ids) - updated_count,
            'operation_type': operation_type
        }
        
        if operation_type in ['date', 'both']:
            summary_stats['new_followup_date'] = new_followup_date
        
        if operation_type in ['user', 'both']:
            from_user = User.query.get(from_user_id) if from_user_id else None
            to_user = User.query.get(to_user_id) if to_user_id else None
            summary_stats['user_transfer'] = {
                'from_user_id': from_user_id,
                'from_user_name': from_user.name if from_user else 'Unknown',
                'to_user_id': to_user_id,
                'to_user_name': to_user.name if to_user else 'Unknown'
            }
        
        return jsonify({
            'success': True,
            'message': f'Successfully updated {updated_count} lead(s)',
            'updated_count': updated_count,
            'total_selected': len(lead_ids),
            'detailed_stats': summary_stats
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in api_admin_leads_manipulation_bulk_update: {e}")
        return jsonify({'error': f'Failed to update leads: {str(e)}'}), 500

@application.route('/admin_leads', methods=['GET', 'POST'])
@login_required
def admin_leads():
    try:
        # Check if user is admin
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            # Handle form submission to add new unassigned lead
            mobile = request.form.get('mobile')
            customer_name = request.form.get('customer_name')
            car_model = request.form.get('car_model')  # Combined manufacturer and model
            pickup_type = request.form.get('pickup_type')
            service_type = request.form.get('service_type')
            source = request.form.get('source')
            remarks = request.form.get('remarks')
            scheduled_date = request.form.get('scheduled_date')
            assign_to = request.form.get('assign_to')
            
            # Convert empty strings to None for database constraints
            customer_name = customer_name.strip() if customer_name else None
            car_model = car_model.strip() if car_model else None
            # Split car_model into manufacturer and model for UnassignedLead table
            car_manufacturer = None
            car_model_split = None
            if car_model:
                # Try to split "Manufacturer Model" format
                parts = car_model.split(' ', 1)
                if len(parts) == 2:
                    car_manufacturer = parts[0].strip()
                    car_model_split = parts[1].strip()
                else:
                    # If only one word, assume it's the model
                    car_model_split = car_model
            pickup_type = pickup_type.strip() if pickup_type else None
            service_type = service_type.strip() if service_type else None
            source = source.strip() if source else None
            remarks = remarks.strip() if remarks else None
            
            # Validate required fields
            if not mobile:
                flash('Mobile number is required', 'error')
                return redirect(url_for('admin_leads'))
            
            # Normalize mobile number
            normalized_mobile = normalize_mobile_number(mobile)
            if not normalized_mobile:
                flash('Invalid mobile number format. Please use: +917404625111, 7404625111, or 917404625111', 'error')
                return redirect(url_for('admin_leads'))
            mobile = normalized_mobile
            
            if not assign_to:
                flash('Please select a team member to assign this lead', 'error')
                return redirect(url_for('admin_leads'))
            
            try:
                # Create new unassigned lead
                new_unassigned_lead = UnassignedLead(
                    mobile=mobile,
                    customer_name=customer_name,
                    car_manufacturer=car_manufacturer,
                    car_model=car_model_split,
                    pickup_type=pickup_type,
                    service_type=service_type,
                    source=source,
                    remarks=remarks,
                    created_at=datetime.now(ist),
                    created_by=current_user.id
                )
                
                # Handle scheduled date
                if scheduled_date:
                    new_unassigned_lead.scheduled_date = ist.localize(datetime.strptime(scheduled_date, '%Y-%m-%d'))
                
                db.session.add(new_unassigned_lead)
                db.session.flush()  # Get the ID of the new lead
                
                # Create team assignment
                today = datetime.now(ist).date()
                new_assignment = TeamAssignment(
                    unassigned_lead_id=new_unassigned_lead.id,
                    assigned_to_user_id=int(assign_to),
                    assigned_date=today,
                    assigned_at=datetime.now(ist),
                    assigned_by=current_user.id,
                    status='Assigned'
                )
                
                db.session.add(new_assignment)
                db.session.commit()
                
                # Send push notification to assigned user
                print(f"\n📤 Attempting to send push notification for lead assignment")
                print(f"   Lead ID: {new_unassigned_lead.id}")
                print(f"   Assigned to User ID: {assign_to}")
                try:
                    send_push_notification(
                        user_id=int(assign_to),
                        title='New Lead Assigned',
                        body=f'A new lead has been assigned to you',
                        url='/todays-leads'
                    )
                except Exception as e:
                    print(f"❌ Exception when calling send_push_notification: {e}")
                    import traceback
                    traceback.print_exc()
                
                flash('Lead added and assigned successfully!', 'success')
                return redirect(url_for('admin_leads'))
                
            except Exception as e:
                db.session.rollback()
                print(f"Error adding unassigned lead: {str(e)}")
                flash('Error adding lead. Please try again.', 'error')
                return redirect(url_for('admin_leads'))
        
        # Handle GET request - display the page
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        created_date = request.args.get('created_date', '')
        
        # Base query for unassigned leads (eager-load assignments and assignees)
        unassigned_query = UnassignedLead.query.options(
            db.joinedload(UnassignedLead.assignments).joinedload(TeamAssignment.assigned_to)
        )
        
        # Apply filters
        if search:
            unassigned_query = unassigned_query.filter(
                db.or_(
                    UnassignedLead.customer_name.ilike(f'%{search}%'),
                    UnassignedLead.mobile.ilike(f'%{search}%'),
                    UnassignedLead.car_manufacturer.ilike(f'%{search}%'),
                    UnassignedLead.car_model.ilike(f'%{search}%')
                )
            )
        
        if created_date:
            try:
                filter_date = datetime.strptime(created_date, '%Y-%m-%d').date()
                start_date = ist.localize(datetime.combine(filter_date, datetime.min.time()))
                end_date = start_date + timedelta(days=1)
                start_date_utc = start_date.astimezone(pytz.UTC)
                end_date_utc = end_date.astimezone(pytz.UTC)
                
                unassigned_query = unassigned_query.filter(
                    UnassignedLead.created_at >= start_date_utc,
                    UnassignedLead.created_at < end_date_utc
                )
            except ValueError:
                pass
        
        # Paginate results
        per_page = 20
        recent_leads_pagination = unassigned_query.order_by(
            UnassignedLead.created_at.desc()
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Get all team members for assignment dropdown
        team_members = User.query.filter_by(is_admin=False).all()
        
        # Calculate team summary data
        team_summary = []
        for member in team_members:
            # Get assigned leads count for today
            today = datetime.now(ist).date()
            assigned_count = TeamAssignment.query.filter(
                TeamAssignment.assigned_to_user_id == member.id,
                TeamAssignment.assigned_date == today
            ).count()
            
            # Get CRM leads count for today
            crm_count = Lead.query.filter(
                Lead.creator_id == member.id,
                Lead.created_at >= ist.localize(datetime.combine(today, datetime.min.time())).astimezone(pytz.UTC),
                Lead.created_at < ist.localize(datetime.combine(today + timedelta(days=1), datetime.min.time())).astimezone(pytz.UTC)
            ).count()
            
            team_summary.append({
                'member': member,
                'assigned_count': assigned_count,
                'crm_count': crm_count
            })
        
        return render_template('admin_leads.html',
            recent_leads_pagination=recent_leads_pagination,
            recent_leads=recent_leads_pagination.items,
            team_members=team_members,
            team_summary=team_summary,
            today_date=datetime.now(ist).date().strftime('%Y-%m-%d'),
            search=search,
            created_date=created_date
        )
        
    except Exception as e:
        print(f"Admin leads error: {str(e)}")
        flash('Error loading admin leads. Please try again.', 'error')
        return redirect(url_for('index'))

@application.route('/team_leads')
@login_required
def team_leads():
    try:
        # Get today's date
        today = datetime.now(ist).date()
        
        # Get assignments for current user for today
        assignments_query = TeamAssignment.query.join(
            UnassignedLead,
            TeamAssignment.unassigned_lead_id == UnassignedLead.id
        ).filter(
            TeamAssignment.assigned_to_user_id == current_user.id,
            TeamAssignment.assigned_date == today
        )
        
        # Apply filters
        created_date = request.args.get('created_date', '')
        search = request.args.get('search', '')
        
        if created_date:
            try:
                filter_date = datetime.strptime(created_date, '%Y-%m-%d').date()
                assignments_query = assignments_query.filter(
                    TeamAssignment.assigned_date == filter_date
                )
            except ValueError:
                pass
        
        if search:
            assignments_query = assignments_query.filter(
                db.or_(
                    UnassignedLead.customer_name.ilike(f'%{search}%'),
                    UnassignedLead.car_manufacturer.ilike(f'%{search}%'),
                    UnassignedLead.car_model.ilike(f'%{search}%')
                )
            )
        
        # Add options to load the unassigned_lead relationship eagerly
        assignments_query = assignments_query.options(
            db.joinedload(TeamAssignment.unassigned_lead)
        )
        
        assignments = assignments_query.order_by(TeamAssignment.assigned_at.desc()).all()
        
        return render_template('team_leads.html',
            assignments=assignments,
            today=today,
            search=search,
            created_date=created_date
        )
        
    except Exception as e:
        print(f"Team leads error: {str(e)}")
        flash('Error loading team leads. Please try again.', 'error')
        return redirect(url_for('index'))

@application.route('/edit_unassigned_lead/<int:lead_id>', methods=['GET', 'POST'])
@login_required
def edit_unassigned_lead(lead_id):
    try:
        # Check if user is admin
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        
        lead = UnassignedLead.query.get_or_404(lead_id)
        
        if request.method == 'POST':
            # Update lead details - convert empty strings to None for database constraints
            lead.customer_name = request.form.get('customer_name').strip() if request.form.get('customer_name') else None
            # Normalize mobile number
            mobile = request.form.get('mobile')
            if mobile:
                normalized_mobile = normalize_mobile_number(mobile)
                if not normalized_mobile:
                    flash('Invalid mobile number format. Please use: +917404625111, 7404625111, or 917404625111', 'error')
                    return render_template('edit_unassigned_lead.html', lead=lead)
                lead.mobile = normalized_mobile
            else:
                lead.mobile = None
            lead.car_manufacturer = request.form.get('car_manufacturer').strip() if request.form.get('car_manufacturer') else None
            lead.car_model = request.form.get('car_model').strip() if request.form.get('car_model') else None
            lead.pickup_type = request.form.get('pickup_type').strip() if request.form.get('pickup_type') else None
            lead.service_type = request.form.get('service_type').strip() if request.form.get('service_type') else None
            lead.source = request.form.get('source').strip() if request.form.get('source') else None
            lead.remarks = request.form.get('remarks').strip() if request.form.get('remarks') else None
            
            # Handle scheduled date
            scheduled_date = request.form.get('scheduled_date')
            if scheduled_date:
                lead.scheduled_date = ist.localize(datetime.strptime(scheduled_date, '%Y-%m-%d'))
            
            # Handle team assignment
            assign_to = request.form.get('assign_to')
            if assign_to:
                # Convert to int since form data comes as string
                assign_to = int(assign_to)
                
                # Check if there's an existing assignment for today
                today = datetime.now(ist).date()
                existing_assignment = TeamAssignment.query.filter(
                    TeamAssignment.unassigned_lead_id == lead.id,
                    TeamAssignment.assigned_date == today
                ).first()
                
                if existing_assignment:
                    if existing_assignment.assigned_to_user_id != assign_to:
                        # Update existing assignment
                        existing_assignment.assigned_to_user_id = assign_to
                        existing_assignment.assigned_at = datetime.now(ist)
                        existing_assignment.assigned_by = current_user.id
                        existing_assignment.status = 'Assigned'  # Reset status for new assignment
                        db.session.commit()
                        # Send push notification to newly assigned user
                        print(f"\n📤 Attempting to send push notification for lead reassignment")
                        print(f"   Lead ID: {lead.id}")
                        print(f"   Reassigned to User ID: {assign_to}")
                        try:
                            send_push_notification(
                                user_id=assign_to,
                                title='Lead Reassigned',
                                body=f'A lead has been reassigned to you',
                                url='/todays-leads'
                            )
                        except Exception as e:
                            print(f"❌ Exception when calling send_push_notification: {e}")
                            import traceback
                            traceback.print_exc()
                        flash('Lead reassigned successfully!', 'success')
                else:
                    # Create new assignment
                    new_assignment = TeamAssignment(
                        unassigned_lead_id=lead.id,
                        assigned_to_user_id=assign_to,
                        assigned_date=today,
                        assigned_at=datetime.now(ist),
                        assigned_by=current_user.id,
                        status='Assigned'
                    )
                    db.session.add(new_assignment)
                    db.session.commit()
                    # Send push notification to assigned user
                    print(f"\n📤 Attempting to send push notification for new lead assignment")
                    print(f"   Lead ID: {lead.id}")
                    print(f"   Assigned to User ID: {assign_to}")
                    try:
                        send_push_notification(
                            user_id=assign_to,
                            title='New Lead Assigned',
                            body=f'A new lead has been assigned to you',
                            url='/todays-leads'
                        )
                    except Exception as e:
                        print(f"❌ Exception when calling send_push_notification: {e}")
                        import traceback
                        traceback.print_exc()
                    flash('Lead assigned successfully!', 'success')
            else:
                # If no team member selected, remove today's assignment if it exists
                today = datetime.now(ist).date()
                existing_assignment = TeamAssignment.query.filter(
                    TeamAssignment.unassigned_lead_id == lead.id,
                    TeamAssignment.assigned_date == today
                ).first()
                
                if existing_assignment:
                    db.session.delete(existing_assignment)
                    flash('Lead unassigned successfully!', 'success')
            
            db.session.commit()
            return redirect(url_for('admin_leads'))
        
        # Get team members for assignment dropdown
        team_members = User.query.filter_by(is_admin=False).all()
        
        # Get current assignment if any
        current_assignment = TeamAssignment.query.filter_by(
            unassigned_lead_id=lead.id
        ).order_by(TeamAssignment.assigned_at.desc()).first()
        
        return render_template('edit_unassigned_lead.html', 
                             lead=lead, 
                             team_members=team_members, 
                             current_assignment=current_assignment)
        
    except Exception as e:
        print(f"Edit unassigned lead error: {str(e)}")
        flash('Error updating lead. Please try again.', 'error')
        return redirect(url_for('admin_leads'))

@application.route('/api/team-leads', methods=['GET'])
@login_required
def api_team_leads():
    """Get team leads assigned to the current user"""
    try:
        # Get date filter from query params
        assigned_date_str = request.args.get('assigned_date', '')
        search = request.args.get('search', '')
        status_filter = request.args.get('status_filter', 'all')  # all, pending, added_to_crm
        
        # Build base query for all assignments (for statistics)
        base_query = TeamAssignment.query.join(
            UnassignedLead,
            TeamAssignment.unassigned_lead_id == UnassignedLead.id
        ).filter(
            TeamAssignment.assigned_to_user_id == current_user.id
        )
        
        # Build filtered query for leads to return
        assignments_query = base_query
        
        # Apply date filter (only if provided)
        if assigned_date_str:
            try:
                filter_date = datetime.strptime(assigned_date_str, '%Y-%m-%d').date()
                assignments_query = assignments_query.filter(
                    TeamAssignment.assigned_date == filter_date
                )
                base_query = base_query.filter(
                    TeamAssignment.assigned_date == filter_date
                )
            except ValueError:
                pass
        
        # Apply search filter
        if search:
            assignments_query = assignments_query.filter(
                db.or_(
                    UnassignedLead.customer_name.ilike(f'%{search}%'),
                    UnassignedLead.car_manufacturer.ilike(f'%{search}%'),
                    UnassignedLead.car_model.ilike(f'%{search}%'),
                    UnassignedLead.mobile.ilike(f'%{search}%')
                )
            )
            base_query = base_query.filter(
                db.or_(
                    UnassignedLead.customer_name.ilike(f'%{search}%'),
                    UnassignedLead.car_manufacturer.ilike(f'%{search}%'),
                    UnassignedLead.car_model.ilike(f'%{search}%'),
                    UnassignedLead.mobile.ilike(f'%{search}%')
                )
            )
        
        # Eager load relationships
        assignments_query = assignments_query.options(
            db.joinedload(TeamAssignment.unassigned_lead)
        )
        base_query = base_query.options(
            db.joinedload(TeamAssignment.unassigned_lead)
        )
        
        # Get all assignments for statistics (before status filter)
        all_assignments = base_query.all()
        
        # Apply status filter to the query for leads to return
        if status_filter == 'pending':
            assignments_query = assignments_query.filter(TeamAssignment.added_to_crm == False)
        elif status_filter == 'added_to_crm':
            assignments_query = assignments_query.filter(TeamAssignment.added_to_crm == True)
        # If status_filter is 'all', no additional filter needed
        
        # Get filtered assignments and sort: pending first (not added_to_crm), then added_to_crm, then by assigned_at desc
        assignments = assignments_query.order_by(
            TeamAssignment.added_to_crm.asc(),  # False (pending) comes before True (added_to_crm)
            TeamAssignment.assigned_at.desc()
        ).all()
        
        # Format response
        leads_data = []
        for assignment in assignments:
            unassigned_lead = assignment.unassigned_lead
            
            # Combine car manufacturer and model
            car_model = None
            if unassigned_lead.car_manufacturer and unassigned_lead.car_model:
                car_model = f"{unassigned_lead.car_manufacturer} {unassigned_lead.car_model}"
            elif unassigned_lead.car_manufacturer:
                car_model = unassigned_lead.car_manufacturer
            elif unassigned_lead.car_model:
                car_model = unassigned_lead.car_model
            
            # Format scheduled date
            scheduled_date_str = ''
            if unassigned_lead.scheduled_date:
                scheduled_date = unassigned_lead.scheduled_date
                # Convert to IST if it has timezone info (likely UTC from database)
                if scheduled_date.tzinfo is not None:
                    # Convert from stored timezone (likely UTC) to IST
                    scheduled_date_ist = scheduled_date.astimezone(ist)
                else:
                    # If no timezone, assume it's already in IST (naive datetime)
                    scheduled_date_ist = ist.localize(scheduled_date)
                # Extract date in IST timezone
                scheduled_date_str = scheduled_date_ist.strftime('%Y-%m-%d')
            
            # Find the CRM lead ID if this assignment was added to CRM
            lead_id = None
            if assignment.added_to_crm:
                # Find the Lead created from this assignment
                # Match by mobile number and creator (the assigned user)
                crm_leads = Lead.query.filter_by(
                    mobile=unassigned_lead.mobile,
                    creator_id=assignment.assigned_to_user_id
                ).order_by(Lead.created_at.desc()).all()
                
                # Find the one closest to processed_at time
                if crm_leads and assignment.processed_at:
                    closest_lead = min(crm_leads, key=lambda l: abs(
                        (l.created_at.replace(tzinfo=pytz.UTC) if l.created_at.tzinfo is None else l.created_at) - 
                        (assignment.processed_at.replace(tzinfo=pytz.UTC) if assignment.processed_at.tzinfo is None else assignment.processed_at)
                    ))
                    lead_id = closest_lead.id
                elif crm_leads:
                    # If no processed_at, just get the most recent one
                    lead_id = crm_leads[0].id
            
            leads_data.append({
                'assignment_id': assignment.id,
                'customer_name': unassigned_lead.customer_name or 'Unknown Customer',
                'mobile': unassigned_lead.mobile,
                'car_model': car_model or '',
                'service_type': unassigned_lead.service_type or '',
                'pickup_type': unassigned_lead.pickup_type or '',
                'scheduled_date': scheduled_date_str,
                'source': unassigned_lead.source or '',
                'status': assignment.status,
                'added_to_crm': assignment.added_to_crm,
                'lead_id': lead_id,  # Include lead_id when added to CRM
                'assigned_at': assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                'assigned_date': assignment.assigned_date.strftime('%Y-%m-%d') if assignment.assigned_date else None
            })
        
        # Calculate statistics from all assignments (not filtered by status)
        total_assigned = len(all_assignments)
        pending = sum(1 for assignment in all_assignments if not assignment.added_to_crm)
        contacted = sum(1 for assignment in all_assignments if assignment.status == 'Contacted')
        added_to_crm = sum(1 for assignment in all_assignments if assignment.added_to_crm)
        
        return jsonify({
            'success': True,
            'leads': leads_data,
            'statistics': {
                'total_assigned': total_assigned,
                'pending': pending,
                'contacted': contacted,
                'added_to_crm': added_to_crm
            }
        })
        
    except Exception as e:
        print(f"Error fetching team leads: {e}")
        return jsonify({'success': False, 'message': 'Error fetching team leads'}), 500

@application.route('/api/team-leads/assignment/<int:assignment_id>', methods=['GET'])
@login_required
def get_assignment_details(assignment_id):
    try:
        # Get the assignment
        assignment = TeamAssignment.query.get_or_404(assignment_id)
        
        # Check if user has permission to view this assignment
        if assignment.assigned_to_user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Permission denied'})
        
        # Check if already added to CRM
        if assignment.added_to_crm:
            return jsonify({'success': False, 'message': 'This lead has already been added to CRM'})
        
        # Get the unassigned lead data
        unassigned_lead = assignment.unassigned_lead
        
        # Get car_model from unassigned_lead (combine manufacturer and model)
        car_model = None
        if unassigned_lead.car_manufacturer and unassigned_lead.car_model:
            car_model = f"{unassigned_lead.car_manufacturer} {unassigned_lead.car_model}"
        elif unassigned_lead.car_manufacturer:
            car_model = unassigned_lead.car_manufacturer
        elif unassigned_lead.car_model:
            car_model = unassigned_lead.car_model
        
        return jsonify({
            'success': True,
            'customer_name': unassigned_lead.customer_name or 'Unknown Customer',
            'mobile': unassigned_lead.mobile,
            'car_registration': '',  # Default empty, user can edit
            'car_model': car_model or '',  # Combined manufacturer and model
            'followup_date': datetime.now(ist).date().strftime('%Y-%m-%d'),  # Default to today
            'status': 'New Lead',  # Default status is always "New Lead" for team leads
            'remarks': ''  # Keep remarks empty by default
        })
        
    except Exception as e:
        print(f"Error fetching assignment details: {e}")
        return jsonify({'success': False, 'message': 'Error fetching assignment details'})

@application.route('/api/team-leads/add-to-crm/<int:assignment_id>', methods=['POST'])
@login_required
def add_to_crm_with_details(assignment_id):
    try:
        data = request.get_json()
        customer_name = data.get('customer_name')
        mobile = data.get('mobile')
        car_registration = data.get('car_registration', '')
        car_model = data.get('car_model', '')
        followup_date = data.get('followup_date')
        status = data.get('status', 'New Lead')
        remarks = data.get('remarks', '')
        
        # Get the assignment
        assignment = TeamAssignment.query.get_or_404(assignment_id)
        
        # Check if user has permission to add this assignment to CRM
        if assignment.assigned_to_user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Permission denied'})
        
        # Check if already added to CRM
        if assignment.added_to_crm:
            return jsonify({'success': False, 'message': 'This lead has already been added to CRM'})
        
        # Validate required fields
        if not customer_name or not mobile:
            return jsonify({'success': False, 'message': 'Customer Name and Mobile Number are required'})
        
        # Normalize mobile number
        normalized_mobile = normalize_mobile_number(mobile)
        if not normalized_mobile:
            return jsonify({'success': False, 'message': 'Invalid mobile number format. Please use: +917404625111, 7404625111, or 917404625111'})
        mobile = normalized_mobile
        
        # Parse followup date
        followup_datetime = datetime.strptime(followup_date, '%Y-%m-%d')
        followup_date_ist = ist.localize(followup_datetime)
        
        # Get car_model from unassigned_lead (combine manufacturer and model) if not provided
        unassigned_lead = assignment.unassigned_lead
        if not car_model:
            if unassigned_lead.car_manufacturer and unassigned_lead.car_model:
                car_model = f"{unassigned_lead.car_manufacturer} {unassigned_lead.car_model}"
            elif unassigned_lead.car_manufacturer:
                car_model = unassigned_lead.car_manufacturer
            elif unassigned_lead.car_model:
                car_model = unassigned_lead.car_model
        
        # Create a new lead in the main CRM system
        new_lead = Lead(
            customer_name=customer_name,
            mobile=mobile,
            car_registration=car_registration,
            car_model=car_model,
            followup_date=followup_date_ist,
            remarks=remarks,
            status=status,
            creator_id=current_user.id,
            created_at=datetime.now(ist),
            modified_at=datetime.now(ist)
        )
        
        # Add the new lead to the database
        db.session.add(new_lead)
        
        # Mark the assignment as added to CRM
        assignment.added_to_crm = True
        assignment.status = 'Added to CRM'
        assignment.processed_at = datetime.now(ist)
        
        # Commit the changes
        db.session.commit()
        
        # Clear any cached queries to ensure fresh data
        db.session.expire_all()
        
        return jsonify({'success': True, 'message': 'Lead successfully added to CRM!'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding to CRM: {str(e)}")
        return jsonify({'success': False, 'message': 'Error adding lead to CRM. Please try again.'})

@application.route('/add_to_crm/<int:assignment_id>', methods=['POST'])
@login_required
def add_to_crm(assignment_id):
    try:
        # Get the assignment
        assignment = TeamAssignment.query.get_or_404(assignment_id)
        
        # Check if user has permission to add this assignment to CRM
        if assignment.assigned_to_user_id != current_user.id:
            flash('Access denied. You can only add your own assigned leads to CRM.', 'error')
            return redirect(url_for('team_leads'))
        
        # Check if already added to CRM
        if assignment.added_to_crm:
            flash('This lead has already been added to CRM.', 'info')
            return redirect(url_for('team_leads'))
        
        # Get the unassigned lead data
        unassigned_lead = assignment.unassigned_lead
        
        # Create a new lead in the main CRM system
        new_lead = Lead(
            customer_name=unassigned_lead.customer_name or 'Unknown Customer',
            mobile=unassigned_lead.mobile,
            car_registration='',  # Can be updated later
            followup_date=datetime.now(ist),  # Default to today
            remarks='',  # Keep remarks empty by default
            status='New Lead',
            creator_id=current_user.id,
            created_at=datetime.now(ist),
            modified_at=datetime.now(ist)
        )
        
        # Add the new lead to the database
        db.session.add(new_lead)
        
        # Mark the assignment as added to CRM
        assignment.added_to_crm = True
        assignment.status = 'Added to CRM'
        assignment.processed_at = datetime.now(ist)
        
        # Commit the changes
        db.session.commit()
        
        flash('Lead successfully added to CRM!', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding to CRM: {str(e)}")
        flash('Error adding lead to CRM. Please try again.', 'error')
    
    return redirect(url_for('team_leads'))

# ==================== NEW FEATURE ROUTES ====================

# Template Management Routes
@application.route('/api/templates', methods=['GET'])
@login_required
def get_templates():
    """Get all available templates for the current user"""
    try:
        # Get global templates and user's personal templates
        templates = Template.query.filter(
            db.or_(
                Template.is_global == True,
                Template.created_by == current_user.id
            )
        ).order_by(Template.category, Template.title).all()
        
        templates_data = [{
            'id': t.id,
            'title': t.title,
            'content': t.content,
            'category': t.category,
            'is_global': t.is_global,
            'usage_count': t.usage_count
        } for t in templates]
        
        return jsonify({'success': True, 'templates': templates_data})
    except Exception as e:
        print(f"Error fetching templates: {e}")
        return jsonify({'success': False, 'message': 'Error fetching templates'})

@application.route('/api/templates/<int:template_id>/use', methods=['POST'])
@login_required
def use_template(template_id):
    """Track template usage"""
    try:
        template = Template.query.get_or_404(template_id)
        template.usage_count += 1
        db.session.commit()
        
        return jsonify({'success': True, 'content': template.content})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error using template'})

@application.route('/api/templates', methods=['POST'])
@login_required
def create_template():
    """Create a new personal template"""
    try:
        data = request.get_json()
        
        new_template = Template(
            title=data.get('title'),
            content=data.get('content'),
            category=data.get('category', 'General'),
            is_global=False,  # Personal templates are not global
            created_by=current_user.id
        )
        
        db.session.add(new_template)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Template created successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error creating template: {e}")
        return jsonify({'success': False, 'message': 'Error creating template'})

# Quick-Log API Routes
@application.route('/api/quick-log/<int:lead_id>', methods=['POST'])
@login_required
def quick_log(lead_id):
    """Quick-log lead update - fast status and remarks update"""
    try:
        data = request.get_json()
        lead = Lead.query.get_or_404(lead_id)
        
        # Check permissions
        if not current_user.is_admin and lead.creator_id != current_user.id:
            return jsonify({'success': False, 'message': 'Permission denied'})
        
        # Store old followup date for tracking
        old_followup_date = lead.followup_date
        
        # Update fields
        if 'status' in data:
            lead.status = data['status']
        
        if 'remarks' in data and data['remarks']:
            # Append new remarks with timestamp
            timestamp = datetime.now(ist).strftime('%Y-%m-%d %H:%M')
            new_remark = f"[{timestamp}] {data['remarks']}"
            if lead.remarks:
                lead.remarks = f"{lead.remarks}\n{new_remark}"
            else:
                lead.remarks = new_remark
        
        if 'followup_date' in data:
            followup_datetime = datetime.strptime(data['followup_date'], '%Y-%m-%d')
            new_followup_date = ist.localize(followup_datetime)
            lead.followup_date = new_followup_date
        
        lead.modified_at = datetime.now(ist)
        db.session.commit()
        
        # Record worked lead if followup date changed
        if old_followup_date != lead.followup_date:
            record_worked_lead(lead_id, current_user.id, old_followup_date, lead.followup_date)
        
        # Log the call activity
        if 'call_duration' in data:
            call_log = CallLog(
                lead_id=lead_id,
                user_id=current_user.id,
                call_type='outgoing',
                call_status=data.get('call_status', 'answered'),
                duration=data.get('call_duration', 0),
                notes=data.get('remarks', ''),
                call_started_at=datetime.now(ist)
            )
            db.session.add(call_log)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Lead updated successfully',
            'lead': {
                'id': lead.id,
                'status': lead.status,
                'followup_date': lead.followup_date.strftime('%Y-%m-%d') if lead.followup_date else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in quick-log: {e}")
        return jsonify({'success': False, 'message': 'Error updating lead'})

# Calling Queue Routes
@application.route('/api/calling-queue', methods=['GET'])
@login_required
def get_calling_queue():
    """Get prioritized calling queue for current user"""
    try:
        today = datetime.now(ist).date()
        target_start = ist.localize(datetime.combine(today, datetime.min.time()))
        target_end = target_start + timedelta(days=1)
        target_start_utc = target_start.astimezone(pytz.UTC)
        target_end_utc = target_end.astimezone(pytz.UTC)
        
        # Get today's followups for current user
        leads = Lead.query.filter(
            Lead.creator_id == current_user.id,
            Lead.followup_date >= target_start_utc,
            Lead.followup_date < target_end_utc
        ).all()
        
        # Calculate scores for each lead
        scored_leads = []
        for lead in leads:
            score = calculate_lead_score(lead)
            scored_leads.append({
                'lead': lead,
                'score': score['total_score'],
                'priority': score['priority']
            })
        
        # Sort by score (highest first)
        scored_leads.sort(key=lambda x: x['score'], reverse=True)
        
        # Convert to JSON
        queue_data = []
        for item in scored_leads[:50]:  # Limit to top 50
            lead = item['lead']
            queue_data.append({
                'id': lead.id,
                'customer_name': lead.customer_name,
                'mobile': lead.mobile,
                'car_registration': lead.car_registration,
                'status': lead.status,
                'remarks': lead.remarks,
                'followup_date': lead.followup_date.strftime('%Y-%m-%d %H:%M') if lead.followup_date else None,
                'score': item['score'],
                'priority': item['priority']
            })
        
        return jsonify({
            'success': True,
            'queue': queue_data,
            'total_count': len(queue_data)
        })
        
    except Exception as e:
        print(f"Error fetching calling queue: {e}")
        return jsonify({'success': False, 'message': 'Error fetching queue'})

def calculate_lead_score(lead):
    """
    Calculate priority score for a lead.
    Score factors:
    - Overdue leads: +50 points
    - Status 'Confirmed': +40 points
    - Status 'Needs Followup': +30 points
    - Recent activity: +20 points
    - First-time lead: +10 points
    """
    score = 0
    
    # Check if overdue - ensure both datetimes are timezone-aware
    now_utc = datetime.now(pytz.UTC)
    if lead.followup_date:
        # Ensure followup_date is timezone-aware
        if lead.followup_date.tzinfo is None:
            # If naive, assume it's UTC
            followup_date_aware = pytz.UTC.localize(lead.followup_date)
        else:
            followup_date_aware = lead.followup_date
        
        if followup_date_aware < now_utc:
            days_overdue = (now_utc - followup_date_aware).days
            score += min(50, 10 * days_overdue)  # Max 50 points
    
    # Status-based score
    status_scores = {
        'Confirmed': 40,
        'Needs Followup': 30,
        'Open': 25,
        'New Lead': 20,
        'Did Not Pick Up': 15,
        'Completed': 5,
        'Feedback': 5
    }
    score += status_scores.get(lead.status, 0)
    
    # Engagement score (has remarks = engaged)
    if lead.remarks and len(lead.remarks) > 50:
        score += 20
    
    # Recency score (recently modified = active)
    if lead.modified_at:
        days_since_modified = (datetime.now(ist) - lead.modified_at).days
        if days_since_modified < 1:
            score += 15
        elif days_since_modified < 3:
            score += 10
    
    # Determine priority
    if score >= 60:
        priority = 'High'
    elif score >= 30:
        priority = 'Medium'
    else:
        priority = 'Low'
    
    return {
        'total_score': score,
        'priority': priority
    }

@application.route('/calling-queue', methods=['GET'])
@login_required
def calling_queue_page():
    """Calling queue page"""
    return render_template('calling_queue.html')

# Advanced Analytics Routes
@application.route('/analytics', methods=['GET'])
@login_required
def analytics_page():
    """Advanced analytics dashboard"""
    try:
        # Date range from request or default to last 30 days
        end_date = request.args.get('end_date', datetime.now(ist).strftime('%Y-%m-%d'))
        start_date = request.args.get('start_date', 
                                      (datetime.now(ist) - timedelta(days=30)).strftime('%Y-%m-%d'))
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        start_utc = ist.localize(datetime.combine(start_dt, datetime.min.time())).astimezone(pytz.UTC)
        end_utc = ist.localize(datetime.combine(end_dt + timedelta(days=1), datetime.min.time())).astimezone(pytz.UTC)
        
        # Get user filter
        user_filter = None
        if current_user.is_admin and request.args.get('user_id'):
            user_filter = int(request.args.get('user_id'))
        elif not current_user.is_admin:
            user_filter = current_user.id
        
        # Build base query
        base_query = Lead.query
        if user_filter:
            base_query = base_query.filter(Lead.creator_id == user_filter)
        
        # 1. Conversion Funnel
        funnel_data = {
            'total_leads': base_query.filter(
                Lead.created_at >= start_utc,
                Lead.created_at < end_utc
            ).count(),
            'contacted': base_query.filter(
                Lead.created_at >= start_utc,
                Lead.created_at < end_utc,
                Lead.status.in_(['Confirmed', 'Needs Followup', 'Completed'])
            ).count(),
            'interested': base_query.filter(
                Lead.created_at >= start_utc,
                Lead.created_at < end_utc,
                Lead.status == 'Confirmed'
            ).count(),
            'converted': base_query.filter(
                Lead.created_at >= start_utc,
                Lead.created_at < end_utc,
                Lead.status == 'Completed'
            ).count()
        }
        
        # 2. Status Distribution
        status_distribution = db.session.query(
            Lead.status,
            db.func.count(Lead.id)
        ).filter(
            Lead.created_at >= start_utc,
            Lead.created_at < end_utc
        )
        if user_filter:
            status_distribution = status_distribution.filter(Lead.creator_id == user_filter)
        status_data = dict(status_distribution.group_by(Lead.status).all())
        
        # 3. Daily Trends
        daily_trends = db.session.query(
            db.func.date(Lead.created_at).label('date'),
            db.func.count(Lead.id).label('count')
        ).filter(
            Lead.created_at >= start_utc,
            Lead.created_at < end_utc
        )
        if user_filter:
            daily_trends = daily_trends.filter(Lead.creator_id == user_filter)
        daily_data = daily_trends.group_by(db.func.date(Lead.created_at)).all()
        
        # 4. User Performance (if admin)
        user_performance = []
        if current_user.is_admin:
            users = User.query.all()
            for user in users:
                user_leads = base_query.filter(
                    Lead.creator_id == user.id,
                    Lead.created_at >= start_utc,
                    Lead.created_at < end_utc
                ).count()
                
                user_completed = base_query.filter(
                    Lead.creator_id == user.id,
                    Lead.created_at >= start_utc,
                    Lead.created_at < end_utc,
                    Lead.status == 'Completed'
                ).count()
                
                conversion_rate = (user_completed / user_leads * 100) if user_leads > 0 else 0
                
                user_performance.append({
                    'name': user.name,
                    'total_leads': user_leads,
                    'completed': user_completed,
                    'conversion_rate': round(conversion_rate, 2)
                })
        
        # 5. Call Analytics (if call logs exist)
        total_calls = CallLog.query.filter(
            CallLog.call_started_at >= start_utc,
            CallLog.call_started_at < end_utc
        )
        if user_filter:
            total_calls = total_calls.filter(CallLog.user_id == user_filter)
        
        call_stats = {
            'total_calls': total_calls.count(),
            'answered': total_calls.filter(CallLog.call_status == 'answered').count(),
            'not_answered': total_calls.filter(CallLog.call_status == 'not_answered').count(),
            'avg_duration': db.session.query(db.func.avg(CallLog.duration)).filter(
                CallLog.call_started_at >= start_utc,
                CallLog.call_started_at < end_utc,
                CallLog.call_status == 'answered'
            ).scalar() or 0
        }
        
        users = User.query.all() if current_user.is_admin else [current_user]
        
        return render_template('analytics.html',
                             funnel_data=funnel_data,
                             status_data=status_data,
                             daily_data=daily_data,
                             user_performance=user_performance,
                             call_stats=call_stats,
                             start_date=start_date,
                             end_date=end_date,
                             users=users)
    
    except Exception as e:
        print(f"Analytics error: {e}")
        flash('Error loading analytics', 'error')
        return redirect(url_for('dashboard'))

# Error handlers
@application.errorhandler(404)
def not_found_error(error):
    # For API routes, return JSON error
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    # For frontend routes, serve the Next.js index.html for client-side routing
    return serve_frontend()

@application.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    # For API routes, return JSON error
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('error.html', error="500 - Internal Server Error"), 500

# Serve Next.js frontend static files
@application.route('/_next/<path:path>')
def serve_next_static(path):
    """Serve Next.js static files from the frontend build"""
    try:
        frontend_static_path = os.path.join(os.path.dirname(__file__), 'static', 'frontend', '_next')
        if os.path.exists(frontend_static_path):
            return send_from_directory(frontend_static_path, path)
        return jsonify({'error': 'Frontend not built'}), 404
    except Exception as e:
        print(f"Error serving Next.js static file: {e}")
        return jsonify({'error': 'Error serving static file'}), 500


def serve_frontend():
    """Serve the Next.js index.html for client-side routing"""
    try:
        frontend_path = os.path.join(os.path.dirname(__file__), 'static', 'frontend')
        index_path = os.path.join(frontend_path, 'index.html')
        
        if os.path.exists(index_path):
            return send_file(index_path)
        else:
            # Fallback to old template if Next.js build doesn't exist
            return render_template('error.html', error="Frontend not built. Please build the Next.js application."), 404
    except Exception as e:
        print(f"Error serving frontend: {e}")
        return render_template('error.html', error="Error loading frontend application."), 500

# Database initialization function
def init_database():
    """Initialize database with tables and default users"""
    try:
        with application.app_context():
            # Create all tables
            db.create_all()
            
            # Check if admin user exists, if not create it
            # If exists, ensure is_admin is True (fix for existing admin users)
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    name='Administrator',
                    is_admin=True
                )
                admin_user.set_password('admin@796!')  # Use set_password to hash it properly
                db.session.add(admin_user)
            else:
                # Ensure existing admin user has is_admin=True
                if not admin_user.is_admin:
                    print(f"⚠️  Admin user found but is_admin was False. Fixing...")
                    admin_user.is_admin = True
                    db.session.commit()
                    print(f"✅ Admin user is_admin field updated to True")
            
            # Create default users if they don't exist
            default_users = [
                {'username': 'hemlata', 'name': 'Hemlata', 'password': 'hemlata123'},
                {'username': 'sneha', 'name': 'Sneha', 'password': 'sneha123'}
            ]
            
            for user_data in default_users:
                existing_user = User.query.filter_by(username=user_data['username']).first()
                if not existing_user:
                    new_user = User(
                        username=user_data['username'],
                        name=user_data['name'],
                        is_admin=False
                    )
                    new_user.set_password(user_data['password'])  # Use set_password to hash it properly
                    db.session.add(new_user)
            
            # Initialize customer name counter if it doesn't exist
            counter = CustomerNameCounter.query.first()
            if not counter:
                counter = CustomerNameCounter(counter=0)
                db.session.add(counter)
                print("✅ Customer name counter initialized")
            
            db.session.commit()
            print("Database initialized successfully")
            
    except Exception as e:
        print(f"Database initialization error: {e}")
        db.session.rollback()

# ==================== PUSH NOTIFICATION FUNCTIONS ====================

def send_push_notification(user_id, title, body, url=None):
    """Send push notification to all subscriptions of a user"""
    timestamp = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'='*60}")
    print(f"[{timestamp}] 🔔 PUSH NOTIFICATION ATTEMPT")
    print(f"{'='*60}")
    print(f"User ID: {user_id}")
    
    try:
        # Get user info for logging
        user = User.query.get(user_id)
        user_name = user.name if user else f"Unknown (ID: {user_id})"
        print(f"User: {user_name} (username: {user.username if user else 'N/A'})")
        
        subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()
        print(f"Found {len(subscriptions)} subscription(s) for user {user_id}")
        
        if not subscriptions:
            print(f"❌ No push subscriptions found for user {user_id} ({user_name})")
            print(f"{'='*60}\n")
            return
        
        # Get VAPID keys from environment
        vapid_private_key = os.getenv('VAPID_PRIVATE_KEY')
        vapid_public_key = os.getenv('VAPID_PUBLIC_KEY')
        vapid_claim_email = os.getenv('VAPID_CLAIM_EMAIL', 'mailto:admin@gaadimech.com')
        
        print(f"VAPID Private Key: {'✅ Present' if vapid_private_key else '❌ Missing'}")
        print(f"VAPID Public Key: {'✅ Present' if vapid_public_key else '❌ Missing'}")
        print(f"VAPID Claim Email: {vapid_claim_email}")
        
        if not vapid_private_key or not vapid_public_key:
            print("❌ VAPID keys not configured. Push notifications disabled.")
            print(f"{'='*60}\n")
            return
        
        # Prepare notification payload
        notification_data = {
            'title': title,
            'body': body,
            'icon': '/icon-192x192.png',  # You can add this icon later
            'badge': '/badge-72x72.png',  # You can add this badge later
            'tag': 'lead-assignment',
            'requireInteraction': False,
            'data': {
                'url': url or '/todays-leads'
            }
        }
        
        print(f"Notification Title: {title}")
        print(f"Notification Body: {body}")
        print(f"Notification URL: {url or '/todays-leads'}")
        
        success_count = 0
        failed_count = 0
        
        for idx, subscription in enumerate(subscriptions, 1):
            print(f"\n--- Processing Subscription {idx}/{len(subscriptions)} ---")
            print(f"Subscription ID: {subscription.id}")
            print(f"Endpoint: {subscription.endpoint[:50]}...")
            print(f"User Agent: {subscription.user_agent or 'N/A'}")
            print(f"Created At: {subscription.created_at}")
            
            try:
                subscription_info = {
                    'endpoint': subscription.endpoint,
                    'keys': {
                        'p256dh': subscription.p256dh,
                        'auth': subscription.auth
                    }
                }
                
                print("Sending webpush...")
                webpush(
                    subscription_info=subscription_info,
                    data=json.dumps(notification_data),
                    vapid_private_key=vapid_private_key,
                    vapid_claims={
                        'sub': vapid_claim_email
                    }
                )
                success_count += 1
                print(f"✅ Successfully sent push notification to subscription {subscription.id}")
            except WebPushException as e:
                print(f"❌ Failed to send push notification to subscription {subscription.id}")
                print(f"   Error: {e}")
                if e.response:
                    print(f"   Response Status: {e.response.status_code}")
                    print(f"   Response Text: {e.response.text[:200]}")
                # If subscription is invalid, remove it
                if e.response and e.response.status_code in [410, 404]:
                    print(f"   🗑️  Removing invalid subscription {subscription.id} (status {e.response.status_code})")
                    db.session.delete(subscription)
                    db.session.commit()
                failed_count += 1
            except Exception as e:
                print(f"❌ Unexpected error sending push notification: {e}")
                import traceback
                traceback.print_exc()
                failed_count += 1
        
        print(f"\n{'='*60}")
        print(f"📊 SUMMARY: {success_count} successful, {failed_count} failed")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error in send_push_notification: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")

@application.route('/api/push/subscribe', methods=['POST', 'OPTIONS'])
@login_required
def api_push_subscribe():
    """Register or update push notification subscription"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept, X-Requested-With, Origin')
        return response
    
    try:
        if not request.is_json:
            return jsonify({'success': False, 'message': 'Invalid request format'}), 400
        
        data = request.get_json()
        endpoint = data.get('endpoint')
        p256dh = data.get('keys', {}).get('p256dh')
        auth = data.get('keys', {}).get('auth')
        user_agent = request.headers.get('User-Agent', '')
        
        if not endpoint or not p256dh or not auth:
            return jsonify({'success': False, 'message': 'Missing required subscription data'}), 400
        
        # Check if subscription already exists
        existing = PushSubscription.query.filter_by(
            user_id=current_user.id,
            endpoint=endpoint
        ).first()
        
        timestamp = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
        if existing:
            # Update existing subscription
            print(f"\n[{timestamp}] 🔄 Updating existing push subscription")
            print(f"   User: {current_user.name} (ID: {current_user.id}, username: {current_user.username})")
            print(f"   Subscription ID: {existing.id}")
            print(f"   Endpoint: {endpoint[:60]}...")
            existing.p256dh = p256dh
            existing.auth = auth
            existing.user_agent = user_agent
            existing.updated_at = datetime.now(ist)
        else:
            # Create new subscription
            print(f"\n[{timestamp}] ✅ New push subscription registered")
            print(f"   User: {current_user.name} (ID: {current_user.id}, username: {current_user.username})")
            print(f"   Endpoint: {endpoint[:60]}...")
            print(f"   User Agent: {user_agent[:100] if user_agent else 'N/A'}")
            subscription = PushSubscription(
                user_id=current_user.id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                user_agent=user_agent
            )
            db.session.add(subscription)
        
        db.session.commit()
        print(f"   ✅ Subscription saved successfully\n")
        return jsonify({'success': True, 'message': 'Push subscription registered successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error registering push subscription: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to register subscription'}), 500

@application.route('/api/push/vapid-public-key', methods=['GET', 'OPTIONS'])
def api_push_vapid_public_key():
    """Get VAPID public key for push notification subscription"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept, X-Requested-With, Origin')
        return response
    
    try:
        vapid_public_key = os.getenv('VAPID_PUBLIC_KEY')
        if not vapid_public_key:
            # Return 200 with empty key instead of 500 - frontend will handle it
            return jsonify({'publicKey': '', 'error': 'VAPID public key not configured'}), 200
        
        return jsonify({'publicKey': vapid_public_key})
    except Exception as e:
        print(f"Error getting VAPID public key: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'publicKey': '', 'error': str(e)}), 200

@application.route('/api/push/unsubscribe', methods=['POST', 'OPTIONS'])
@login_required
def api_push_unsubscribe():
    """Remove push notification subscription"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept, X-Requested-With, Origin')
        return response
    
    try:
        if not request.is_json:
            return jsonify({'success': False, 'message': 'Invalid request format'}), 400
        
        data = request.get_json()
        endpoint = data.get('endpoint')
        
        if not endpoint:
            return jsonify({'success': False, 'message': 'Missing endpoint'}), 400
        
        # Find and delete subscription
        subscription = PushSubscription.query.filter_by(
            user_id=current_user.id,
            endpoint=endpoint
        ).first()
        
        if subscription:
            db.session.delete(subscription)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Push subscription removed successfully'})
        else:
            return jsonify({'success': False, 'message': 'Subscription not found'}), 404
        
    except Exception as e:
        db.session.rollback()
        print(f"Error removing push subscription: {e}")
        return jsonify({'success': False, 'message': 'Failed to remove subscription'}), 500

@application.route('/api/push/debug/subscriptions', methods=['GET'])
@login_required
def api_push_debug_subscriptions():
    """Debug endpoint to check push notification subscriptions for current user or specified user (admin only)"""
    try:
        # Get user_id from query params (admin only) or use current user
        user_id_param = request.args.get('user_id', type=int)
        
        if user_id_param:
            # Only admins can check other users' subscriptions
            if not current_user.is_admin:
                return jsonify({'error': 'Admin access required to check other users'}), 403
            target_user_id = user_id_param
        else:
            target_user_id = current_user.id
        
        # Get user info
        user = User.query.get(target_user_id)
        if not user:
            return jsonify({'error': f'User {target_user_id} not found'}), 404
        
        # Get subscriptions
        subscriptions = PushSubscription.query.filter_by(user_id=target_user_id).all()
        
        # Check VAPID keys
        vapid_private_key = os.getenv('VAPID_PRIVATE_KEY')
        vapid_public_key = os.getenv('VAPID_PUBLIC_KEY')
        vapid_claim_email = os.getenv('VAPID_CLAIM_EMAIL', 'mailto:admin@gaadimech.com')
        
        subscriptions_data = []
        for sub in subscriptions:
            subscriptions_data.append({
                'id': sub.id,
                'endpoint': sub.endpoint,
                'endpoint_short': sub.endpoint[:50] + '...' if len(sub.endpoint) > 50 else sub.endpoint,
                'user_agent': sub.user_agent,
                'created_at': sub.created_at.isoformat() if sub.created_at else None,
                'has_p256dh': bool(sub.p256dh),
                'has_auth': bool(sub.auth),
            })
        
        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'name': user.name
            },
            'subscriptions_count': len(subscriptions),
            'subscriptions': subscriptions_data,
            'vapid_config': {
                'private_key_configured': bool(vapid_private_key),
                'public_key_configured': bool(vapid_public_key),
                'claim_email': vapid_claim_email,
                'public_key_preview': vapid_public_key[:50] + '...' if vapid_public_key and len(vapid_public_key) > 50 else vapid_public_key
            }
        })
    except Exception as e:
        print(f"Error in api_push_debug_subscriptions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@application.route('/api/push/debug/user-by-username', methods=['GET'])
@login_required
def api_push_debug_user_by_username():
    """Debug endpoint to find user by username and check their subscriptions (admin only)"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        username = request.args.get('username')
        if not username:
            return jsonify({'error': 'username parameter required'}), 400
        
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': f'User with username "{username}" not found'}), 404
        
        # Get subscriptions
        subscriptions = PushSubscription.query.filter_by(user_id=user.id).all()
        
        subscriptions_data = []
        for sub in subscriptions:
            subscriptions_data.append({
                'id': sub.id,
                'endpoint_short': sub.endpoint[:80] + '...' if len(sub.endpoint) > 80 else sub.endpoint,
                'user_agent': sub.user_agent,
                'created_at': sub.created_at.isoformat() if sub.created_at else None,
            })
        
        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'name': user.name
            },
            'subscriptions_count': len(subscriptions),
            'subscriptions': subscriptions_data
        })
    except Exception as e:
        print(f"Error in api_push_debug_user_by_username: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize database when application starts
    try:
        init_database()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        import traceback
        traceback.print_exc()
    
    # Start scheduler for daily snapshots
    # Note: In production with gunicorn, this will run in each worker
    # Consider using a separate scheduler process or Redis-based locking
    scheduler_instance = init_scheduler()
    
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting application on port {port}")
    
    try:
        # Run without debug mode for better stability
        application.run(host='0.0.0.0', port=port, debug=False)
    finally:
        # Shutdown scheduler on app exit
        if scheduler_instance:
            scheduler_instance.shutdown() 