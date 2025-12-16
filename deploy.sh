#!/bin/bash
# AWS Elastic Beanstalk Deployment Script for Free Tier
# This script helps deploy the backend to AWS EB

set -e  # Exit on error

echo "🚀 GaadiMech CRM Backend - AWS Deployment Script"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if EB CLI is installed
if ! command -v eb &> /dev/null; then
    echo -e "${RED}❌ EB CLI is not installed.${NC}"
    echo "Install it with: pip install awsebcli"
    exit 1
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${YELLOW}⚠️  AWS CLI not found in PATH${NC}"
    echo "AWS CLI is recommended but not required for EB CLI"
fi

# Check AWS credentials (workaround: check file existence instead of CLI test)
if [ -f ~/.aws/credentials ]; then
    echo -e "${GREEN}✅ AWS credentials file found${NC}"
else
    echo -e "${RED}❌ AWS credentials not configured.${NC}"
    echo "Credentials file not found at: ~/.aws/credentials"
    echo "Run: aws configure"
    exit 1
fi

# Optional: Try to verify credentials (non-blocking)
if command -v aws &> /dev/null; then
    if aws sts get-caller-identity &> /dev/null; then
        echo -e "${GREEN}✅ AWS credentials verified${NC}"
    else
        echo -e "${YELLOW}⚠️  Could not verify AWS credentials via CLI${NC}"
        echo "Continuing anyway - EB CLI will handle authentication"
    fi
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"
echo ""

# Check if EB is initialized
if [ ! -f ".elasticbeanstalk/config.yml" ]; then
    echo -e "${YELLOW}⚠️  EB not initialized. Initializing...${NC}"
    read -p "Enter AWS region (default: ap-south-1): " region
    region=${region:-ap-south-1}

    eb init -p python-3.11 GaadiMech-CRM-Backend --region "$region"
    echo -e "${GREEN}✅ EB initialized${NC}"
    echo ""
fi

# Check if environment exists
echo "Checking for existing environment..."
ENV_NAME="GaadiMech-CRM-Backend-env-alb"
ENV_EXISTS=false

# Try to check if environment exists (workaround for EB CLI execution issues)
if [ -f ".elasticbeanstalk/config.yml" ]; then
    CONFIG_ENV=$(grep "environment:" .elasticbeanstalk/config.yml | awk '{print $2}' | head -1)
    if [ -n "$CONFIG_ENV" ]; then
        ENV_NAME="$CONFIG_ENV"
        ENV_EXISTS=true
        echo -e "${GREEN}✅ Environment found in config: ${ENV_NAME}${NC}"
    fi
fi

# Try to verify via EB CLI (non-blocking)
if command -v eb &> /dev/null; then
    if eb list 2>/dev/null | grep -q "$ENV_NAME\|GaadiMech-CRM-Backend-env"; then
        ENV_EXISTS=true
        echo -e "${GREEN}✅ Environment exists: ${ENV_NAME}${NC}"
    fi
fi

if [ "$ENV_EXISTS" = true ]; then
    echo -e "${GREEN}✅ Deploying to existing environment: ${ENV_NAME}${NC}"
    echo ""
else
    echo -e "${YELLOW}⚠️  Environment does not exist. Creating...${NC}"
    read -p "Enter AWS region (default: ap-south-1): " region
    region=${region:-ap-south-1}

    eb create "$ENV_NAME" \
        --instance-type t2.micro \
        --single \
        --region "$region"
    echo -e "${GREEN}✅ Environment created${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Set environment variables before deploying!${NC}"
    echo "Run the following commands or set them via AWS Console:"
    echo ""
    echo "eb setenv RDS_HOST=your-rds-endpoint"
    echo "eb setenv RDS_DB=your_database_name"
    echo "eb setenv RDS_USER=your_database_user"
    echo "eb setenv RDS_PASSWORD=your_database_password"
    echo "eb setenv RDS_PORT=5432"
    echo "eb setenv SECRET_KEY=your-secret-key"
    echo "eb setenv FLASK_ENV=production"
    echo ""
    read -p "Have you set the environment variables? (y/n): " vars_set
    if [ "$vars_set" != "y" ]; then
        echo "Please set environment variables first, then run this script again."
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}📦 Deploying application to ${ENV_NAME}...${NC}"
if [ "$ENV_EXISTS" = true ] && [ -n "$ENV_NAME" ]; then
    eb deploy "$ENV_NAME"
else
    eb deploy
fi

echo ""
echo -e "${GREEN}✅ Deployment initiated!${NC}"
echo ""
echo -e "${YELLOW}⏳ Waiting 30 seconds for deployment to stabilize...${NC}"
sleep 30

echo ""
echo -e "${GREEN}📋 Checking deployment status...${NC}"
eb status

echo ""
echo -e "${YELLOW}⏳ Waiting additional 30 seconds before checking logs...${NC}"
sleep 30

echo ""
echo -e "${GREEN}📊 Fetching recent logs...${NC}"
echo "=========================================="
eb logs --all | tail -n 100
echo "=========================================="

echo ""
echo -e "${GREEN}🏥 Checking health status...${NC}"
eb health --refresh

echo ""
echo -e "${GREEN}🔍 Checking application health endpoint...${NC}"
APP_URL=$(eb status | grep "CNAME" | awk '{print $2}' | head -n 1)
if [ -n "$APP_URL" ]; then
    echo "Testing health endpoint: http://${APP_URL}/health"
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "http://${APP_URL}/health" || echo "000")
    if [ "$HEALTH_RESPONSE" = "200" ]; then
        echo -e "${GREEN}✅ Health endpoint responding (HTTP 200)${NC}"
    else
        echo -e "${YELLOW}⚠️  Health endpoint returned HTTP ${HEALTH_RESPONSE}${NC}"
        echo "This might be normal if the application is still starting up."
    fi
else
    echo -e "${YELLOW}⚠️  Could not determine application URL${NC}"
fi

echo ""
echo -e "${GREEN}✅ Deployment verification complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Check detailed logs: eb logs --all"
echo "2. Stream logs in real-time: eb logs --stream"
echo "3. Open application: eb open"
echo "4. Check status: eb status"
echo "5. Test API endpoints"
echo ""
echo -e "${YELLOW}⚠️  Don't forget to:${NC}"
echo "- Verify RDS security group allows connections from EB"
echo "- Run database migrations if needed: eb ssh (then flask db upgrade)"
echo "- Update EB_ORIGIN after frontend deployment"
echo "- Monitor health status: eb health --refresh"

