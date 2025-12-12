# AWS Elastic Beanstalk Deployment Guide (Free Tier)

This guide walks you through deploying the GaadiMech CRM Backend to AWS Elastic Beanstalk using free tier resources.

## Prerequisites

1. **AWS Account** with free tier eligibility (first 12 months)
2. **AWS CLI** installed and configured
   ```bash
   aws --version
   aws configure
   ```
3. **EB CLI** installed
   ```bash
   pip install awsebcli
   ```
4. **AWS RDS PostgreSQL** instance already running (as mentioned)
5. **Git** (for version control)

## Free Tier Resources Used

- **EC2 Instance**: t2.micro (750 hours/month free for first 12 months)
- **Elastic Beanstalk**: Free (you only pay for underlying resources)
- **CloudWatch Logs**: 5GB free per month
- **Data Transfer**: 15GB outbound free per month

**Estimated Monthly Cost**: $0 (within free tier limits)

## Step 1: Initialize Elastic Beanstalk Application

```bash
cd GaadiMech-CRM-Backend

# Initialize EB (if not already done)
eb init -p python-3.11 GaadiMech-CRM-Backend --region ap-south-1
```

When prompted:
- Select a region: `ap-south-1` (or your preferred region)
- Application name: `GaadiMech-CRM-Backend`
- Python version: `3.11`

## Step 2: Create Environment with Free Tier Configuration

```bash
# Create environment with free tier settings
eb create GaadiMech-CRM-Backend-env \
  --instance-type t2.micro \
  --single \
  --region ap-south-1
```

The `--single` flag creates a single-instance environment (no load balancer) to minimize costs.

## Step 3: Configure Environment Variables

### Option A: Using AWS Console (Recommended for sensitive values)

1. Go to [AWS Elastic Beanstalk Console](https://console.aws.amazon.com/elasticbeanstalk)
2. Select your environment: `GaadiMech-CRM-Backend-env`
3. Go to **Configuration** → **Software** → **Edit**
4. Add the following environment properties:

```
RDS_HOST=crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com
RDS_DB=crmportal
RDS_USER=crmadmin
RDS_PASSWORD=GaadiMech2024!
RDS_PORT=5432
SECRET_KEY=GaadiMech-Super-Secret-Key-Change-This-2024
FLASK_ENV=development
PORT=5000
ENABLE_SCHEDULER=true
```

5. Click **Apply** and wait for the environment to update

### Option B: Using AWS CLI

```bash
# Set environment variables
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

### Option C: Using EB CLI

```bash
eb setenv RDS_HOST=crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com
eb setenv RDS_DB=crmportal
eb setenv RDS_USER=crmadmin
eb setenv RDS_PASSWORD=GaadiMech2024!
eb setenv RDS_PORT=5432
eb setenv SECRET_KEY=GaadiMech-Super-Secret-Key-Change-This-2024
eb setenv FLASK_ENV=development
eb setenv PORT=5000
eb setenv ENABLE_SCHEDULER=true
```

## Step 4: Configure RDS Security Group

Ensure your RDS instance security group allows inbound connections from your EB environment:

1. Go to **RDS Console** → Your database → **Connectivity & security**
2. Click on the **Security group** link
3. Go to **Inbound rules** → **Edit inbound rules**
4. Add rule:
   - Type: PostgreSQL
   - Port: 5432
   - Source: Select the security group of your EB environment (or use `0.0.0.0/0` for testing, but restrict in production)

## Step 5: Deploy Application

```bash
# Deploy to EB
eb deploy

# Or deploy to specific environment
eb deploy GaadiMech-CRM-Backend-env
```

## Step 6: Run Database Migrations

Migrations should run automatically via the pre-deploy hook, but you can verify:

```bash
# SSH into the instance
eb ssh

# Once inside, run migrations
cd /var/app/current
source /var/app/venv/*/bin/activate
flask db upgrade
exit
```

## Step 7: Verify Deployment

```bash
# Check environment status
eb status

# View logs
eb logs

# Open application in browser
eb open
```

## Step 8: Test API Endpoints

After deployment, test your API endpoints:

```bash
# Get the application URL
eb status | grep CNAME

# Test health endpoint (if available)
curl http://your-app.elasticbeanstalk.com/api/health

# Test login endpoint
curl -X POST http://your-app.elasticbeanstalk.com/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"your_username","password":"your_password"}'
```

## Configuration Files Overview

The deployment uses these configuration files:

- `.ebextensions/01_python.config`: Python and WSGI configuration
- `.ebextensions/02_database.config`: Database environment setup
- `.ebextensions/03_nginx.config`: Nginx proxy settings
- `.ebextensions/04_free_tier.config`: Free tier instance configuration
- `.ebextensions/05_environment_vars.config`: Environment variables documentation
- `.platform/hooks/predeploy/01_migrate.sh`: Pre-deployment migration hook
- `Procfile`: Gunicorn process definition (optimized for free tier)

## Updating CORS After Frontend Deployment

Once your frontend is deployed on Railway, update the CORS origin:

```bash
eb setenv EB_ORIGIN=https://your-frontend.railway.app
```

Or via AWS Console:
- Configuration → Software → Environment properties
- Add/Update: `EB_ORIGIN=https://your-frontend.railway.app`

## Monitoring and Logs

```bash
# View recent logs
eb logs

# View specific log files
eb logs --all

# Stream logs in real-time
eb logs --stream

# Check environment health
eb health
```

## Troubleshooting

### Database Connection Issues

1. Verify RDS security group allows EB security group
2. Check environment variables are set correctly:
   ```bash
   eb printenv
   ```
3. Check application logs:
   ```bash
   eb logs
   ```

### Application Not Starting

1. Check logs for errors:
   ```bash
   eb logs
   ```
2. Verify Procfile syntax
3. Check Python version matches `runtime.txt`
4. Verify all dependencies in `requirements.txt` are compatible

### Out of Memory Issues

If you encounter memory issues on t2.micro:
- The Procfile is already optimized for 1 worker
- Consider upgrading to t3.micro (still free tier eligible) if needed
- Check for memory leaks in application code

### Migration Failures

1. SSH into instance:
   ```bash
   eb ssh
   ```
2. Run migrations manually:
   ```bash
   cd /var/app/current
   source /var/app/venv/*/bin/activate
   flask db upgrade
   ```

## Cost Optimization Tips

1. **Use Single Instance**: Already configured (no load balancer)
2. **Minimal Log Retention**: Set to 3 days in config
3. **Monitor Usage**: Check AWS Billing Dashboard regularly
4. **Stop When Not Needed**: You can stop the environment when not in use:
   ```bash
   eb terminate GaadiMech-CRM-Backend-env
   ```
   (Note: This will delete the environment. For temporary stops, consider using EB environment suspension)

## Next Steps

After successful backend deployment and testing:

1. ✅ Verify all API endpoints are working
2. ✅ Test database connections
3. ✅ Verify authentication works
4. ✅ Deploy frontend on Railway
5. ✅ Update CORS origin with Railway frontend URL
6. ✅ Test end-to-end integration

## Useful Commands

```bash
# List all environments
eb list

# Check environment status
eb status

# View environment info
eb printenv

# SSH into instance
eb ssh

# Open application
eb open

# View logs
eb logs

# Update environment variables
eb setenv KEY=value

# Deploy new version
eb deploy

# Terminate environment (careful!)
eb terminate
```

## Support

For issues:
1. Check AWS Elastic Beanstalk logs
2. Check CloudWatch logs
3. Review application logs via `eb logs`
4. Verify all environment variables are set correctly

