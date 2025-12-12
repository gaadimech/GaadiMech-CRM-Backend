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
    echo -e "${RED}❌ AWS CLI is not installed.${NC}"
    echo "Install it from: https://aws.amazon.com/cli/"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured.${NC}"
    echo "Run: aws configure"
    exit 1
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
if eb list | grep -q "GaadiMech-CRM-Backend-env"; then
    echo -e "${GREEN}✅ Environment exists${NC}"
    read -p "Deploy to existing environment? (y/n): " deploy_existing
    if [ "$deploy_existing" != "y" ]; then
        echo "Exiting..."
        exit 0
    fi
else
    echo -e "${YELLOW}⚠️  Environment does not exist. Creating...${NC}"
    read -p "Enter AWS region (default: ap-south-1): " region
    region=${region:-ap-south-1}
    
    eb create GaadiMech-CRM-Backend-env \
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
echo -e "${GREEN}📦 Deploying application...${NC}"
eb deploy

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Check logs: eb logs"
echo "2. Open application: eb open"
echo "3. Check status: eb status"
echo "4. Test API endpoints"
echo ""
echo -e "${YELLOW}⚠️  Don't forget to:${NC}"
echo "- Verify RDS security group allows connections from EB"
echo "- Run database migrations if needed: eb ssh (then flask db upgrade)"
echo "- Update EB_ORIGIN after frontend deployment"

