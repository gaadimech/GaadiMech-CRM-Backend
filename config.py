"""
Configuration and Flask application initialization.
This module handles all app setup, database configuration, and extensions.
"""
import os
import sys
from urllib.parse import quote_plus
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from pytz import timezone

# Load environment variables
load_dotenv()

# Timezone
ist = timezone('Asia/Kolkata')

# Initialize Flask app
application = Flask(__name__)
application.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'GaadiMech2024!')

# Configure CORS for frontend API requests
IS_PRODUCTION = os.getenv('FLASK_ENV') == 'production' or os.getenv('EB_ENVIRONMENT') is not None

if IS_PRODUCTION:
    # For production: Use exact Elastic Beanstalk origin with credentials support
    EB_ORIGIN_STR = os.getenv('EB_ORIGIN', 'http://gaadimech-crm-unified.eba-ftgmu9fp.ap-south-1.elasticbeanstalk.com')
    EB_ORIGINS = [origin.strip() for origin in EB_ORIGIN_STR.split(',') if origin.strip()]
    print(f"CORS configured for origins: {EB_ORIGINS}")
    CORS(application,
         origins=EB_ORIGINS,
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
         allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With", "Origin"],
         supports_credentials=True,
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

# Database configuration
RDS_HOST = os.getenv("RDS_HOST", "crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com")
RDS_DB = os.getenv("RDS_DB", "crmportal")
RDS_USER = os.getenv("RDS_USER", "crmadmin")
RDS_PASSWORD = os.getenv("RDS_PASSWORD", "GaadiMech2024!")
RDS_PORT = os.getenv("RDS_PORT", "5432")

# URL-encode the password to handle special characters
RDS_PASSWORD_ENCODED = quote_plus(RDS_PASSWORD)

# Build DATABASE_URL from individual components
DATABASE_URL = f"postgresql+psycopg2://{RDS_USER}:{RDS_PASSWORD_ENCODED}@{RDS_HOST}:{RDS_PORT}/{RDS_DB}"

# Debug: Print actual password being used (without exposing full password)
print(f"RDS Password (first 5 chars): {RDS_PASSWORD[:5]}...")
print(f"RDS Password Encoded: {RDS_PASSWORD_ENCODED[:10]}...")

# Validate that we're using the correct database hostname
if "gaadimech-crm-db" in DATABASE_URL:
    print(f"ERROR: Wrong database hostname detected! Fixing...")
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
application.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'pool_recycle': 1800,
    'pool_pre_ping': True,
    'connect_args': {
        'connect_timeout': 30,
        'sslmode': 'require'
    }
}

# Session configuration
IS_PRODUCTION = os.getenv('FLASK_ENV') == 'production'
FORCE_HTTPS = os.getenv('FORCE_HTTPS', 'false').lower() == 'true'
USE_SECURE_COOKIES = FORCE_HTTPS or (IS_PRODUCTION and os.getenv('USE_SECURE_COOKIES', 'false').lower() == 'true')

application.config.update(
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_DOMAIN=None,
    REMEMBER_COOKIE_SECURE=False,
    REMEMBER_COOKIE_HTTPONLY=True,
    # Extended session duration: 30 days for remember cookie and permanent sessions
    # Users will stay logged in for 30 days unless they explicitly log out
    REMEMBER_COOKIE_DURATION=timedelta(days=3),
    PERMANENT_SESSION_LIFETIME=timedelta(days=3)
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

# Simple cache
dashboard_cache_store = {}

# Test database connection on startup
def test_database_connection():
    """Test database connection on application startup"""
    try:
        from sqlalchemy import text
        with application.app_context():
            db.session.execute(text("SELECT 1"))
            db.session.commit()
            print("✅ Database connection test successful")
            return True
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test connection when module is imported
test_database_connection()

