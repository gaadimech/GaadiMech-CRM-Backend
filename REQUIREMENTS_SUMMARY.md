# Python Application Requirements Summary

## Overview
This document lists all required Python packages and libraries to run `application.py` in the GaadiMech CRM Backend.

## Virtual Environment
- **Location**: `venv/` directory in the backend folder
- **Python Version**: 3.9.6 (or compatible)
- **Status**: ✅ All dependencies installed

## Required Packages (from requirements.txt)

### Core Flask Framework
- **Flask==2.3.3** - Main web framework
- **Flask-SQLAlchemy==3.0.5** - Database ORM integration
- **Flask-Login==0.6.3** - User session management
- **Flask-Migrate==4.1.0** - Database migrations
- **Flask-Limiter==3.5.0** - Rate limiting
- **Flask-CORS==4.0.0** - Cross-origin resource sharing
- **Werkzeug==2.3.7** - WSGI utilities (Flask dependency)

### Database
- **psycopg2-binary==2.9.9** - PostgreSQL database adapter
- **SQLAlchemy==2.0.41** - SQL toolkit and ORM

### Security & Environment
- **python-dotenv==1.0.0** - Environment variable management
- **requests==2.31.0** - HTTP library for external API calls

### Timezone & Scheduling
- **pytz==2023.3.post1** - Timezone definitions
- **APScheduler==3.11.0** - Advanced Python Scheduler for background tasks

### Performance & Caching
- **redis==5.0.1** - Redis client (for caching/rate limiting)
- **Flask-Caching==2.1.0** - Caching support for Flask

### Production Server
- **gunicorn==21.2.0** - Production WSGI HTTP server

### Development Tools (Optional)
- **memory-profiler==0.61.0** - Memory usage profiling

## Key Imports Used in application.py

```python
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from flask_limiter import Limiter
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
```

## Installation Instructions

### 1. Activate Virtual Environment
```bash
cd GaadiMech-CRM-Backend
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows
```

### 2. Install All Requirements
```bash
pip install -r requirements.txt
```

### 3. Verify Installation
```bash
pip list | grep Flask
pip list | grep SQLAlchemy
```

## Running the Application

### Option 1: Using run_local.py (Recommended)
```bash
source venv/bin/activate
python run_local.py
```
This script sets up all environment variables and runs the application.

### Option 2: Direct execution
```bash
source venv/bin/activate
python application.py
```
Note: You'll need to set environment variables manually or use a `.env` file.

### Option 3: Using Gunicorn (Production)
```bash
source venv/bin/activate
gunicorn -w 4 -b 0.0.0.0:5000 application:application
```

## Environment Variables Required

The application needs these environment variables (set in `run_local.py` or `.env` file):

- `DATABASE_URL` - PostgreSQL connection string
- `RDS_HOST` - Database hostname
- `RDS_DB` - Database name
- `RDS_USER` - Database username
- `RDS_PASSWORD` - Database password
- `RDS_PORT` - Database port (default: 5432)
- `SECRET_KEY` - Flask secret key for sessions
- `FLASK_ENV` - Environment mode (development/production)
- `PORT` - Server port (default: 5000)

## Dependencies Breakdown

### Required for Basic Operation
- Flask, Flask-SQLAlchemy, Flask-Login, Flask-CORS
- psycopg2-binary, SQLAlchemy
- python-dotenv, Werkzeug

### Required for Full Features
- Flask-Migrate (database migrations)
- Flask-Limiter (rate limiting)
- APScheduler (background tasks)
- pytz (timezone handling)

### Optional but Recommended
- redis, Flask-Caching (performance)
- gunicorn (production server)
- requests (external API calls)

### Development Only
- memory-profiler (debugging)

## Total Package Count
- **Core packages**: 34+ packages installed
- **Total dependencies**: Includes all transitive dependencies

## Verification
All packages have been successfully installed in the virtual environment. You can verify by running:
```bash
source venv/bin/activate
python -c "import flask; import flask_sqlalchemy; import psycopg2; print('All imports successful!')"
```


