# Complete File Structure Guide

## 📁 Overview of File Organization

The application has been refactored from a single 7000+ line file into a modular structure. Here's how everything is organized:

```
GaadiMech-CRM-Backend/
├── application.py              # 🚀 MAIN ENTRY POINT - Run this to start the app
├── application_backup.py       # 📦 Backup of original file (safety)
│
├── config.py                   # ⚙️ Configuration & Flask Setup
├── models.py                   # 🗄️ Database Models
├── utils.py                    # 🔧 Utility Functions
│
├── routes/                     # 🛣️ Route Handlers (API Endpoints)
│   ├── __init__.py
│   ├── auth.py                # Authentication routes
│   └── common.py              # Common utilities
│
├── services/                   # 💼 Business Logic Services
│   ├── __init__.py
│   └── database.py            # Database initialization
│
├── run_local.py               # 🏃 Local development runner
├── Procfile                   # 📋 Production deployment config
└── requirements.txt           # 📦 Python dependencies
```

---

## 📄 File-by-File Breakdown

### 1. **`application.py`** - Main Entry Point
**Purpose**: The main Flask application file that ties everything together.

**What it does**:
- Imports and initializes all modules
- Registers route blueprints
- Sets up request/response handlers
- Contains routes that haven't been moved yet (temporary)
- Runs the Flask server

**When to edit**:
- ✅ To register new route blueprints
- ✅ To add application-level middleware
- ✅ To add error handlers
- ✅ To configure startup/shutdown logic
- ❌ Don't add new routes here (use route modules instead)
- ❌ Don't add business logic here (use services instead)

**Key sections**:
```python
# Imports from new modules
from config import application, db, login_manager, limiter
from models import User, Lead, ...
from routes.auth import auth_bp

# Register blueprints
application.register_blueprint(auth_bp)

# Request handlers
@application.after_request
@application.teardown_request

# Routes (temporary - will be moved to route modules)
@application.route('/api/leads', ...)
```

**How to run**:
```bash
python application.py
# OR
python run_local.py
```

---

### 2. **`config.py`** - Configuration & Setup
**Purpose**: All Flask configuration, database setup, and extension initialization.

**What it does**:
- Creates the Flask application instance
- Configures database connection (PostgreSQL)
- Sets up CORS (Cross-Origin Resource Sharing)
- Configures session cookies
- Initializes Flask extensions (SQLAlchemy, LoginManager, Rate Limiter)
- Tests database connection on startup

**When to edit**:
- ✅ To change database connection settings
- ✅ To modify CORS configuration
- ✅ To change session/cookie settings
- ✅ To add new Flask extensions
- ✅ To modify rate limiting settings
- ❌ Don't add routes here
- ❌ Don't add business logic here

**Key exports**:
```python
application  # Flask app instance
db          # SQLAlchemy database
login_manager  # Flask-Login manager
limiter     # Rate limiter
ist         # IST timezone
```

**Example usage in other files**:
```python
from config import application, db, limiter

@application.route('/api/example')
@limiter.limit("10 per minute")
def example():
    # Use db here
    pass
```

---

### 3. **`models.py`** - Database Models
**Purpose**: All SQLAlchemy database models (tables).

**What it does**:
- Defines all database tables as Python classes
- Sets up relationships between tables
- Defines constraints and indexes
- Provides model methods (e.g., `User.check_password()`)

**When to edit**:
- ✅ To add a new database table/model
- ✅ To modify existing table structure
- ✅ To add relationships between tables
- ✅ To add model methods (e.g., `to_dict()`)
- ✅ To add database constraints
- ❌ Don't add routes here
- ❌ Don't add business logic here (use services)

**Available models**:
- `User` - User accounts
- `Lead` - Customer leads
- `UnassignedLead` - Unassigned leads
- `TeamAssignment` - Team assignments
- `DailyFollowupCount` - Daily followup tracking
- `WorkedLead` - Worked lead tracking
- `Template` - Message templates
- `LeadScore` - Lead scoring
- `CallLog` - Call history
- `WhatsAppTemplate` - WhatsApp templates
- `CustomerNameCounter` - Name counter
- `TeleobiTemplateCache` - Template cache
- `WhatsAppSend` - WhatsApp send tracking
- `WhatsAppBulkJob` - Bulk job tracking
- `PushSubscription` - Push notification subscriptions

**Example**:
```python
from models import User, Lead

# Query users
users = User.query.all()

# Create a new lead
lead = Lead(
    customer_name="John Doe",
    mobile="1234567890",
    followup_date=datetime.now(),
    creator_id=current_user.id
)
db.session.add(lead)
db.session.commit()
```

---

### 4. **`utils.py`** - Utility Functions
**Purpose**: Reusable helper functions used throughout the application.

**What it does**:
- Provides utility functions for common operations
- Handles data formatting and conversion
- Provides helper functions for mobile numbers, dates, etc.

**When to edit**:
- ✅ To add new utility functions
- ✅ To modify existing utility functions
- ✅ To add data validation helpers
- ✅ To add formatting functions
- ❌ Don't add routes here
- ❌ Don't add database queries here (use models/services)

**Available functions**:
- `normalize_mobile_number(mobile)` - Normalizes phone numbers
- `utc_to_ist(utc_dt)` - Converts UTC to IST
- `to_ist_iso(dt)` - Converts datetime to IST ISO string

**Example**:
```python
from utils import normalize_mobile_number, utc_to_ist

# Normalize phone number
phone = normalize_mobile_number("+919876543210")  # Returns "9876543210"

# Convert timezone
ist_time = utc_to_ist(utc_datetime)
```

---

### 5. **`routes/` Directory** - Route Handlers
**Purpose**: All API endpoints and route handlers organized by feature.

#### **`routes/auth.py`** - Authentication Routes
**Purpose**: Handles user authentication (login, logout, session management).

**When to edit**:
- ✅ To modify login logic
- ✅ To add new authentication endpoints
- ✅ To change logout behavior
- ✅ To add password reset functionality
- ✅ To modify session handling

**Current routes**:
- `POST /login` - User login
- `GET /logout` - User logout
- `GET /api/user/current` - Get current user info

**Example of adding a new route**:
```python
from flask import Blueprint, request, jsonify
from flask_login import login_required
from config import db
from models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/user/profile', methods=['GET'])
@login_required
def get_profile():
    return jsonify({'user': current_user.name})
```

#### **`routes/common.py`** - Common Utilities
**Purpose**: Shared route utilities (e.g., serving frontend).

**When to edit**:
- ✅ To modify frontend serving logic
- ✅ To add shared route utilities

---

### 6. **`services/` Directory** - Business Logic
**Purpose**: Business logic and service functions (separate from routes).

#### **`services/database.py`** - Database Service
**Purpose**: Database initialization and setup functions.

**When to edit**:
- ✅ To modify database initialization
- ✅ To add default data creation
- ✅ To add database migration helpers
- ✅ To modify user creation logic

**Functions**:
- `init_database()` - Initialize database with tables and default users

---

## 🎯 Quick Reference: Which File to Edit?

### Adding a New Feature

| What You're Adding | File to Edit |
|-------------------|--------------|
| **New API endpoint** | `routes/[feature].py` (create new or use existing) |
| **New database table** | `models.py` |
| **New utility function** | `utils.py` |
| **New business logic** | `services/[feature].py` |
| **New configuration** | `config.py` |
| **Register new routes** | `application.py` (register blueprint) |

### Modifying Existing Features

| What You're Modifying | File to Edit |
|----------------------|--------------|
| **Login/logout logic** | `routes/auth.py` |
| **Database table structure** | `models.py` |
| **API endpoint behavior** | `routes/[feature].py` |
| **Business logic** | `services/[feature].py` |
| **Database connection** | `config.py` |
| **Utility functions** | `utils.py` |

### Examples

**Example 1: Adding a new "Reports" feature**
1. Create `routes/reports.py` with report endpoints
2. Create `services/reports.py` with report generation logic
3. Register blueprint in `application.py`:
   ```python
   from routes.reports import reports_bp
   application.register_blueprint(reports_bp)
   ```

**Example 2: Adding a new database field**
1. Edit `models.py` to add the field:
   ```python
   class Lead(db.Model):
       # ... existing fields ...
       new_field = db.Column(db.String(100))
   ```
2. Create a migration (using Alembic):
   ```bash
   flask db migrate -m "Add new_field to Lead"
   flask db upgrade
   ```

**Example 3: Adding a new utility function**
1. Edit `utils.py`:
   ```python
   def format_currency(amount):
       return f"₹{amount:,.2f}"
   ```
2. Use it in routes:
   ```python
   from utils import format_currency
   ```

---

## 🏃 Running the Application Locally

### Option 1: Using `run_local.py` (Recommended)
```bash
cd GaadiMech-CRM-Backend
python run_local.py
```

### Option 2: Direct Python
```bash
cd GaadiMech-CRM-Backend
python application.py
```

### Option 3: Using Flask CLI
```bash
cd GaadiMech-CRM-Backend
export FLASK_APP=application.py
flask run
```

### Option 4: Using Gunicorn (Production-like)
```bash
cd GaadiMech-CRM-Backend
gunicorn application:application
```

### What Happens When You Run:

1. **Configuration loads** (`config.py`):
   - Database connection is established
   - CORS is configured
   - Extensions are initialized

2. **Database is initialized** (`services/database.py`):
   - Tables are created (if they don't exist)
   - Default users are created (admin, hemlata, sneha)

3. **Routes are registered** (`application.py`):
   - Blueprints from `routes/` are registered
   - All endpoints become available

4. **Server starts**:
   - Default port: 5000
   - Access at: `http://localhost:5000`

### Environment Variables Needed:

Create a `.env` file in `GaadiMech-CRM-Backend/`:
```env
SECRET_KEY=your-secret-key
RDS_HOST=your-database-host
RDS_DB=your-database-name
RDS_USER=your-database-user
RDS_PASSWORD=your-database-password
RDS_PORT=5432
FLASK_ENV=development
```

---

## 🔄 Workflow: Adding a New Feature

Let's say you want to add a "Notifications" feature:

### Step 1: Create the Route Module
Create `routes/notifications.py`:
```python
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from config import db
from models import Notification

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).all()
    return jsonify({
        'notifications': [n.to_dict() for n in notifications]
    })
```

### Step 2: Create the Service (if needed)
Create `services/notifications.py`:
```python
from config import db
from models import Notification, User

def create_notification(user_id, message):
    notification = Notification(
        user_id=user_id,
        message=message
    )
    db.session.add(notification)
    db.session.commit()
    return notification
```

### Step 3: Add Model (if needed)
Edit `models.py`:
```python
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.Text)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(ist))
```

### Step 4: Register the Blueprint
Edit `application.py`:
```python
from routes.notifications import notifications_bp
application.register_blueprint(notifications_bp)
```

### Step 5: Test
```bash
python run_local.py
# Test the endpoint
curl http://localhost:5000/api/notifications
```

---

## 📝 Best Practices

1. **Keep routes thin**: Routes should only handle HTTP request/response. Business logic goes in services.

2. **Use blueprints**: Always organize routes into blueprints by feature.

3. **Import from config**: Always import `application`, `db`, etc. from `config.py`, don't create new instances.

4. **Use models for queries**: Don't write raw SQL, use SQLAlchemy models.

5. **Keep utilities pure**: Utility functions should be pure functions (no side effects).

6. **Test after changes**: Always test locally after making changes.

---

## 🐛 Troubleshooting

### Import Errors
If you get import errors:
```python
# Make sure you're importing from the right place
from config import application, db  # ✅ Correct
from application import db  # ❌ Wrong
```

### Database Connection Issues
- Check `.env` file has correct database credentials
- Verify database is running
- Check `config.py` for connection settings

### Routes Not Working
- Make sure blueprint is registered in `application.py`
- Check route decorators are correct
- Verify imports are correct

---

## 📚 Summary

- **`application.py`**: Main entry point - run this to start the app
- **`config.py`**: Configuration - edit for settings
- **`models.py`**: Database models - edit for database structure
- **`utils.py`**: Utilities - edit for helper functions
- **`routes/`**: Routes - edit for API endpoints
- **`services/`**: Services - edit for business logic

**To run locally**: `python run_local.py` or `python application.py`

The structure is designed to make it easy to find and edit code by feature, making development much more manageable! 🎉

