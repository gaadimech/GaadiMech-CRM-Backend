#!/bin/bash
# Set AWS Elastic Beanstalk Environment Variables
# This script sets environment variables from the local configuration

set -e

echo "🔧 Setting AWS Elastic Beanstalk Environment Variables"
echo "======================================================"
echo ""

# Check if EB CLI is installed
if ! command -v eb &> /dev/null; then
    echo "❌ EB CLI is not installed. Install it with: pip install awsebcli"
    exit 1
fi

# Check if environment exists
if ! eb list | grep -q "GaadiMech-CRM-Backend-env"; then
    echo "❌ Environment 'GaadiMech-CRM-Backend-env' does not exist."
    echo "Create it first with: eb create GaadiMech-CRM-Backend-env --instance-type t2.micro --single"
    exit 1
fi

# Environment variables from .env file
RDS_HOST="crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com"
RDS_DB="crmportal"
RDS_USER="crmadmin"
RDS_PASSWORD="GaadiMech2024!"
RDS_PORT="5432"
SECRET_KEY="GaadiMech-Super-Secret-Key-Change-This-2024"
FLASK_ENV="development"
PORT="5000"
ENABLE_SCHEDULER="true"

echo "Setting environment variables..."
echo ""

# Set all environment variables at once
eb setenv \
  RDS_HOST="$RDS_HOST" \
  RDS_DB="$RDS_DB" \
  RDS_USER="$RDS_USER" \
  RDS_PASSWORD="$RDS_PASSWORD" \
  RDS_PORT="$RDS_PORT" \
  SECRET_KEY="$SECRET_KEY" \
  FLASK_ENV="$FLASK_ENV" \
  PORT="$PORT" \
  ENABLE_SCHEDULER="$ENABLE_SCHEDULER"

echo ""
echo "✅ Environment variables set successfully!"
echo ""
echo "Note: EB_ORIGIN will need to be set after frontend deployment on Railway"
echo "You can set it later with:"
echo "  eb setenv EB_ORIGIN=https://your-frontend.railway.app"
echo ""
echo "To verify, run: eb printenv"

