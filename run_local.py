#!/usr/bin/env python3
import os

# Set environment variables
os.environ['DATABASE_URL'] = 'postgresql://crmadmin:GaadiMech2024!@crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com:5432/crmportal'
os.environ['RDS_HOST'] = 'crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com'
os.environ['RDS_DB'] = 'crmportal'
os.environ['RDS_USER'] = 'crmadmin'
os.environ['RDS_PASSWORD'] = 'GaadiMech2024!'
os.environ['RDS_PORT'] = '5432'
os.environ['SECRET_KEY'] = 'GaadiMech-Super-Secret-Key-Change-This-2024'
os.environ['FLASK_ENV'] = 'development'
os.environ['PORT'] = '5000'

# Import the application
from application import application as app

if __name__ == '__main__':
    print("🚀 Starting GaadiMech CRM locally...")
    print("📍 Database: crm-portal-db")
    print("🌐 Server: http://localhost:5000")
    print("=" * 50)
    
    # Run the app without the scheduler setup
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
