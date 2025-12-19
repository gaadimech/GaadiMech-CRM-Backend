# AWS Deployment Guide - Refactored Codebase

## ✅ Pre-Deployment Status

**All checks passed!** The refactored codebase is ready for deployment.

- ✅ All modules working correctly
- ✅ Application imports successful
- ✅ Gunicorn can start the application
- ✅ All required files present
- ✅ Procfile configured correctly

---

## 🚀 Deployment Steps

### Step 1: Run Pre-Deployment Check
```bash
cd GaadiMech-CRM-Backend
./pre_deploy_check.sh
```

**Expected Output**: ✅ ALL CHECKS PASSED

### Step 2: Verify Environment Variables in AWS

Before deploying, ensure these environment variables are set in AWS Elastic Beanstalk:

```bash
# Check current environment variables
eb printenv

# Set environment variables if needed
eb setenv \
  RDS_HOST=your-rds-host \
  RDS_DB=your-database-name \
  RDS_USER=your-database-user \
  RDS_PASSWORD=your-database-password \
  RDS_PORT=5432 \
  SECRET_KEY=your-secret-key \
  FLASK_ENV=production \
  EB_ORIGIN=your-frontend-url
```

### Step 3: Deploy to AWS

**Option A: Using deploy.sh script (Recommended)**
```bash
./deploy.sh
```

**Option B: Manual deployment**
```bash
eb deploy
```

### Step 4: Monitor Deployment

The deployment will take 3-5 minutes. Monitor progress:

```bash
# Watch deployment status
eb status

# Stream logs in real-time
eb logs --stream
```

---

## 📊 Post-Deployment Verification

### 1. Check Deployment Status
```bash
eb status
```

**Look for**:
- Status: `Ready` (green)
- Health: `Ok` (green)
- CNAME: Your application URL

### 2. Check Application Logs

```bash
# Get recent logs
eb logs --all | tail -100

# Or stream logs
eb logs --stream
```

### 3. Analyze Logs for Success Indicators

**✅ Success Indicators** (Look for these in logs):
```
✅ Database connection test successful
✅ Database initialized successfully
✅ Application imports successful
✅ Blueprints registered
✅ Gunicorn started
✅ Worker processes started
✅ Application is running
```

**❌ Error Indicators** (Watch for these):
```
❌ ModuleNotFoundError → Missing file
❌ ImportError → Import path issue
❌ Database connection failed → RDS config issue
❌ Blueprint registration failed → Route issue
❌ Worker timeout → Startup issue
```

### 4. Test Health Endpoint

```bash
# Get application URL
APP_URL=$(eb status | grep "CNAME" | awk '{print $2}')

# Test health endpoint
curl http://${APP_URL}/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-12-19T..."
}
```

### 5. Test Authentication Endpoint

```bash
# Test current user (should return 401 - this is correct)
curl -v http://${APP_URL}/api/user/current

# Test login
curl -X POST http://${APP_URL}/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin@796!"}'
```

---

## 🔍 Log Analysis Guide

### Understanding Deployment Logs

#### Successful Startup Sequence:
```
1. Database connection test successful
2. Database initialized successfully
3. Application imports successful
4. Blueprints registered
5. Gunicorn started
6. Worker processes started
7. Application listening on port 5000
```

#### Common Error Patterns:

**Error 1: Module Not Found**
```
ModuleNotFoundError: No module named 'config'
```
**Solution**: Ensure `config.py` is in root directory

**Error 2: Import Error**
```
ImportError: cannot import name 'application' from 'config'
```
**Solution**: Check `config.py` exports `application`

**Error 3: Database Connection Failed**
```
Database connection test failed
```
**Solution**: Check RDS environment variables and security groups

**Error 4: Blueprint Not Found**
```
ModuleNotFoundError: No module named 'routes.auth'
```
**Solution**: Ensure `routes/` directory is included

---

## 🛠️ Quick Troubleshooting

### If Deployment Fails:

1. **Check Logs Immediately**:
   ```bash
   eb logs --all | tail -200
   ```

2. **Verify Files Deployed**:
   ```bash
   eb ssh
   ls -la  # Check files
   ls -la routes/  # Check routes directory
   ls -la services/  # Check services directory
   exit
   ```

3. **Test Import on Server**:
   ```bash
   eb ssh
   python3 -c "from application import application; print('OK')"
   exit
   ```

4. **Redeploy**:
   ```bash
   eb deploy
   ```

### If Application Starts But Routes Don't Work:

1. **Check Blueprint Registration**:
   ```bash
   eb logs --all | grep -i "blueprint\|route"
   ```

2. **Verify Routes Directory**:
   ```bash
   eb ssh
   ls -la routes/
   cat routes/__init__.py
   exit
   ```

3. **Check Application.py**:
   ```bash
   eb ssh
   grep "register_blueprint" application.py
   exit
   ```

---

## 📋 Deployment Checklist

Before deploying:
- [ ] Pre-deployment check passed
- [ ] Environment variables set in AWS
- [ ] RDS security group allows EB connections
- [ ] All files present (config.py, models.py, utils.py, routes/, services/)
- [ ] Procfile correct
- [ ] requirements.txt up to date

After deploying:
- [ ] Deployment status: Ready
- [ ] Health status: Ok
- [ ] Logs show successful startup
- [ ] Health endpoint returns 200
- [ ] Authentication endpoints work
- [ ] Database connection successful
- [ ] No errors in logs

---

## 🎯 Key Points for Refactored Codebase

### What Changed:
- ✅ Models moved to `models.py`
- ✅ Config moved to `config.py`
- ✅ Utils moved to `utils.py`
- ✅ Auth routes moved to `routes/auth.py`
- ✅ Database service moved to `services/database.py`

### What Stays the Same:
- ✅ `application.py` is still the entry point
- ✅ Procfile still uses `application:application`
- ✅ Gunicorn still works the same way
- ✅ Deployment process unchanged

### What to Verify:
- ✅ All modular files are included in deployment
- ✅ Imports work correctly on server
- ✅ Blueprints are registered
- ✅ Database connection works

---

## 📞 Post-Deployment Commands

```bash
# Check status
eb status

# View logs
eb logs --all

# Stream logs
eb logs --stream

# Check health
eb health --refresh

# Open application
eb open

# SSH into instance
eb ssh

# View environment variables
eb printenv
```

---

## ✅ Success Criteria

Deployment is successful when:
1. ✅ Status shows "Ready" (green)
2. ✅ Health shows "Ok" (green)
3. ✅ Logs show successful startup
4. ✅ Health endpoint returns 200
5. ✅ Authentication works
6. ✅ Database connection works
7. ✅ No errors in logs

---

**Ready to deploy!** 🚀

Run `./deploy.sh` or `eb deploy` to start deployment.

