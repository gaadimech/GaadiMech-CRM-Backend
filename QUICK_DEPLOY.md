# Quick AWS Deployment Guide

## Step 1: Initialize EB (if not done)

```bash
cd GaadiMech-CRM-Backend
eb init -p python-3.11 GaadiMech-CRM-Backend --region ap-south-1
```

## Step 2: Create Environment

```bash
eb create GaadiMech-CRM-Backend-env --instance-type t2.micro --single --region ap-south-1
```

## Step 3: Set Environment Variables

### Option A: Use the automated script (Easiest)

```bash
./set_aws_env.sh
```

### Option B: Manual command

```bash
eb setenv \
  RDS_HOST=crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com \
  RDS_DB=crmportal \
  RDS_USER=crmadmin \
  RDS_PASSWORD=GaadiMech2024! \
  RDS_PORT=5432 \
  SECRET_KEY=GaadiMech-Super-Secret-Key-Change-This-2024 \
  FLASK_ENV=development \
  PORT=5000 \
  ENABLE_SCHEDULER=true
```

## Step 4: Configure RDS Security Group

Ensure your RDS security group allows inbound connections from your EB environment security group on port 5432.

## Step 5: Deploy

```bash
eb deploy
```

## Step 6: Verify

```bash
# Check status
eb status

# View logs
eb logs

# Open application
eb open
```

## After Frontend Deployment

Once frontend is deployed on Railway, set the CORS origin:

```bash
eb setenv EB_ORIGIN=https://your-frontend.railway.app
```

## Environment Variables Summary

| Variable | Value |
|----------|-------|
| RDS_HOST | crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com |
| RDS_DB | crmportal |
| RDS_USER | crmadmin |
| RDS_PASSWORD | GaadiMech2024! |
| RDS_PORT | 5432 |
| SECRET_KEY | GaadiMech-Super-Secret-Key-Change-This-2024 |
| FLASK_ENV | development |
| PORT | 5000 |
| ENABLE_SCHEDULER | true |

