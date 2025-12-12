# Manual AWS Environment Variables Setup

Based on your local configuration from `run_local.py`, here are the environment variables to set in AWS:

## Environment Variables to Set

### Using EB CLI (Recommended)

Run this command from the `GaadiMech-CRM-Backend` directory:

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

### Or Use the Automated Script

```bash
./set_aws_env.sh
```

### Using AWS Console

1. Go to [AWS Elastic Beanstalk Console](https://console.aws.amazon.com/elasticbeanstalk)
2. Select your environment: `GaadiMech-CRM-Backend-env`
3. Go to **Configuration** → **Software** → **Edit**
4. Add these environment properties:

| Key | Value |
|-----|-------|
| `RDS_HOST` | `crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com` |
| `RDS_DB` | `crmportal` |
| `RDS_USER` | `crmadmin` |
| `RDS_PASSWORD` | `GaadiMech2024!` |
| `RDS_PORT` | `5432` |
| `SECRET_KEY` | `GaadiMech-Super-Secret-Key-Change-This-2024` |
| `FLASK_ENV` | `development` |
| `PORT` | `5000` |
| `ENABLE_SCHEDULER` | `true` |

5. Click **Apply**

## After Frontend Deployment

Once your frontend is deployed on Railway, add:

```bash
eb setenv EB_ORIGIN=https://your-frontend.railway.app
```

Or via AWS Console, add:
- Key: `EB_ORIGIN`
- Value: `https://your-frontend.railway.app`

## Verify Environment Variables

```bash
eb printenv
```

This will show all currently set environment variables.

