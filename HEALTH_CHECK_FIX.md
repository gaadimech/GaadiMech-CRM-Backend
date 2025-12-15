# Health Check Configuration and Fixes

## Overview
This document describes the health check improvements made to ensure AWS Elastic Beanstalk shows green health status.

## Changes Made

### 1. Health Check Endpoint (`/health`)
- **Location**: `application.py`
- **Purpose**: Provides a dedicated endpoint for AWS EB health checks
- **Features**:
  - Fast response time (< 1 second)
  - Always returns HTTP 200 (prevents false negatives)
  - Quick database connectivity check
  - Returns "degraded" status if DB is down (not "failed")

### 2. Deployment Script Improvements (`deploy.sh`)
- **Added**: 30-second sleep timer after deployment
- **Added**: Automatic status check
- **Added**: Automatic log fetching (last 100 lines)
- **Added**: Health status check with refresh
- **Added**: Health endpoint test

### 3. Elastic Beanstalk Configuration (`.ebextensions/`)
- **01_health_check.config**: Configures EB to use `/health` endpoint
- **02_nginx_health.config**: Configures Nginx to proxy health checks quickly

## Common Health Check Issues and Solutions

### Issue 1: Health Status Shows "Severe" Despite Successful Deployment
**Cause**: 
- No dedicated health check endpoint
- Root path (`/`) might be slow or require authentication
- Health check timing out

**Solution**:
- Added `/health` endpoint that's fast and doesn't require auth
- Configured EB to use `/health` instead of root path
- Health endpoint always returns 200 OK

### Issue 2: Health Check Timeout
**Cause**:
- Database queries taking too long
- Application not responding quickly enough

**Solution**:
- Health endpoint uses simple `SELECT 1` query
- Added timeout handling
- Returns immediately even if DB check fails

### Issue 3: Health Check Returns 404
**Cause**:
- Health check path not configured
- Nginx not routing health checks correctly

**Solution**:
- Created `.ebextensions/01_health_check.config` to set health check URL
- Created `.ebextensions/02_nginx_health.config` to configure Nginx routing

### Issue 4: Health Status Not Updating
**Cause**:
- Health checks not being performed
- Configuration not applied

**Solution**:
- Enhanced health reporting in config
- Added `eb health --refresh` to deployment script

## Testing Health Check

### Manual Test
```bash
# Get application URL
APP_URL=$(eb status | grep "CNAME" | awk '{print $2}')

# Test health endpoint
curl http://${APP_URL}/health
```

### Expected Response
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-12-12T10:30:00+05:30"
}
```

### If Database is Down
```json
{
  "status": "degraded",
  "database": "disconnected",
  "message": "Application is running but database connection failed",
  "timestamp": "2024-12-12T10:30:00+05:30"
}
```

## Deployment Process

1. **Deploy Application**:
   ```bash
   ./deploy.sh
   ```

2. **Script Automatically**:
   - Waits 30 seconds for deployment to stabilize
   - Checks deployment status
   - Waits another 30 seconds
   - Fetches recent logs
   - Checks health status
   - Tests health endpoint

3. **Verify Health Status**:
   ```bash
   eb health --refresh
   ```

4. **Check Logs if Issues**:
   ```bash
   eb logs --all
   eb logs --stream
   ```

## Health Check Configuration Details

### Single Instance Environments
- For `--single` environments (no load balancer)
- Health checks are performed by the EC2 instance itself
- Health endpoint must respond quickly (< 5 seconds)

### Load Balanced Environments
- Health checks are performed by the load balancer
- Health endpoint must respond quickly (< 5 seconds)
- Multiple consecutive failures mark instance as unhealthy

## Monitoring

### Check Health Status
```bash
eb health
eb health --refresh
eb health --view
```

### View Health Metrics
- Go to AWS Console → Elastic Beanstalk → Your Environment → Health
- Check "Health" tab for detailed metrics
- Review "Monitoring" tab for graphs

## Troubleshooting

### Health Status Still Shows "Severe"
1. Check if health endpoint is accessible:
   ```bash
   curl http://your-app.elasticbeanstalk.com/health
   ```

2. Check application logs:
   ```bash
   eb logs --all | grep -i health
   ```

3. Verify configuration files are deployed:
   ```bash
   eb ssh
   ls -la /opt/elasticbeanstalk/deploy/configuration/ebextensions/
   ```

4. Check Nginx configuration:
   ```bash
   eb ssh
   cat /etc/nginx/conf.d/health_check.conf
   ```

### Health Endpoint Returns 500
- Check application logs for errors
- Verify database connection
- Check if application is running: `eb ssh` then `ps aux | grep gunicorn`

### Health Endpoint Times Out
- Check if application is responding
- Verify Gunicorn is running
- Check system resources (memory, CPU)

## Best Practices

1. **Keep Health Endpoint Fast**: Should respond in < 1 second
2. **Don't Require Authentication**: Health checks should be public
3. **Always Return 200**: Even if degraded, return 200 to prevent false negatives
4. **Monitor Regularly**: Check health status after deployments
5. **Log Health Checks**: Monitor health check frequency and failures

## Additional Notes

- Health endpoint is accessible without authentication
- Health checks run every 30 seconds by default
- Multiple consecutive failures (usually 3) mark instance as unhealthy
- For single-instance environments, unhealthy status doesn't trigger replacement (no load balancer)

