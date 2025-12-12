# Environment Variables Reference

This document lists all environment variables required for the GaadiMech CRM Backend.

## Required Variables

### Database Configuration

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `RDS_HOST` | RDS PostgreSQL endpoint | `crm-portal-db.xxxxx.ap-south-1.rds.amazonaws.com` | ✅ Yes |
| `RDS_DB` | Database name | `crmportal` | ✅ Yes |
| `RDS_USER` | Database username | `crmadmin` | ✅ Yes |
| `RDS_PASSWORD` | Database password | `YourSecurePassword123!` | ✅ Yes |
| `RDS_PORT` | Database port | `5432` | ✅ Yes |

### Application Configuration

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `SECRET_KEY` | Flask secret key for sessions | `your-super-secret-key-here` | ✅ Yes |
| `FLASK_ENV` | Environment mode | `production` or `development` | ✅ Yes |

## Optional Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `EB_ORIGIN` | Frontend origin for CORS | `http://localhost:3000` | ❌ No |
| `ENABLE_SCHEDULER` | Enable background scheduler | `true` | ❌ No |
| `FORCE_HTTPS` | Force HTTPS redirects | `false` | ❌ No |
| `USE_SECURE_COOKIES` | Use secure cookies | `false` | ❌ No |
| `PORT` | Server port (local only) | `5000` | ❌ No |

## Setting Variables for AWS Deployment

### Method 1: AWS Console (Recommended for sensitive values)

1. Go to [AWS Elastic Beanstalk Console](https://console.aws.amazon.com/elasticbeanstalk)
2. Select your environment
3. Go to **Configuration** → **Software** → **Edit**
4. Add variables under **Environment properties**
5. Click **Apply**

### Method 2: EB CLI

```bash
# Set individual variables
eb setenv RDS_HOST=your-rds-endpoint
eb setenv RDS_DB=your_database_name
eb setenv RDS_USER=your_database_user
eb setenv RDS_PASSWORD=your_database_password
eb setenv RDS_PORT=5432
eb setenv SECRET_KEY=your-secret-key
eb setenv FLASK_ENV=production

# Or set multiple at once
eb setenv \
  RDS_HOST=your-rds-endpoint \
  RDS_DB=your_database_name \
  RDS_USER=your_database_user \
  RDS_PASSWORD=your_database_password \
  RDS_PORT=5432 \
  SECRET_KEY=your-secret-key \
  FLASK_ENV=production
```

### Method 3: AWS CLI

```bash
aws elasticbeanstalk update-environment \
  --environment-name GaadiMech-CRM-Backend-env \
  --option-settings \
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=RDS_HOST,Value=your-rds-endpoint \
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=RDS_DB,Value=your_database_name
```

## Viewing Current Variables

```bash
# Using EB CLI
eb printenv

# Using AWS CLI
aws elasticbeanstalk describe-configuration-settings \
  --application-name GaadiMech-CRM-Backend \
  --environment-name GaadiMech-CRM-Backend-env \
  --query 'ConfigurationSettings[0].OptionSettings[?Namespace==`aws:elasticbeanstalk:application:environment`]'
```

## Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use AWS Secrets Manager** or **Parameter Store** for production secrets (optional)
3. **Rotate secrets regularly**, especially `SECRET_KEY` and `RDS_PASSWORD`
4. **Use different values** for development and production
5. **Restrict access** to environment variables in AWS Console

## Local Development

For local development, create a `.env` file in the backend directory:

```bash
cp .env.example .env
# Edit .env with your local values
```

The application will automatically load variables from `.env` using `python-dotenv`.

