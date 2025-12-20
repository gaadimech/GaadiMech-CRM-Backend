# AWS Deployment Checklist - Refactored Codebase

## ✅ Pre-Deployment Verification

### 1. Code Structure Verification
- ✅ Models in `models.py` (no duplicates)
- ✅ Config in `config.py` (no duplicates)
- ✅ Utils in `utils.py` (no duplicates)
- ✅ Routes modularized (auth routes in `routes/auth.py`)
- ✅ Services modularized (database in `services/database.py`)
- ✅ Application imports from all modules correctly
- ✅ No circular imports
- ✅ Application runs locally successfully

### 2. Procfile Verification
- ✅ Procfile uses: `gunicorn ... application:application`
- ✅ `application` is imported from `config.py` in `application.py`
- ✅ Gunicorn can import `application` correctly
- ✅ All dependencies in `requirements.txt`

### 3. Files to Deploy
Ensure these files are included:
- ✅ `application.py` (main entry point)
- ✅ `config.py` (configuration)
- ✅ `models.py` (database models)
- ✅ `utils.py` (utilities)
- ✅ `routes/` directory (route modules)
  - ✅ `routes/__init__.py`
  - ✅ `routes/auth.py`
  - ✅ `routes/common.py`
- ✅ `services/` directory (service modules)
  - ✅ `services/__init__.py`
  - ✅ `services/database.py`
- ✅ `Procfile` (gunicorn configuration)
- ✅ `requirements.txt` (dependencies)
- ✅ `runtime.txt` (Python version)
- ✅ `migrations/` directory (database migrations)
- ✅ Other supporting files (teleobi_client.py, text_parser.py, etc.)

### 4. Files NOT to Deploy (Optional)
- ⚠️ `application_backup.py` (backup file - can exclude)
- ⚠️ `test_*.py` (test files - can exclude)
- ⚠️ `venv/` (virtual environment - should NOT be deployed)
- ⚠️ Documentation files (`.md` files - optional)

---

## 🚀 Deployment Steps

### Step 1: Verify Local Application Works
```bash
cd GaadiMech-CRM-Backend
source venv/bin/activate
python application.py
# Test that it starts without errors
```

### Step 2: Test Gunicorn Locally (Optional but Recommended)
```bash
gunicorn --workers=1 --threads=2 --worker-class=gthread --timeout=120 application:application
# Test that gunicorn can start the application
```

### Step 3: Check Environment Variables
Ensure these are set in AWS Elastic Beanstalk:
- `RDS_HOST` - Database hostname
- `RDS_DB` - Database name
- `RDS_USER` - Database username
- `RDS_PASSWORD` - Database password
- `RDS_PORT` - Database port (usually 5432)
- `SECRET_KEY` - Flask secret key
- `FLASK_ENV` - Set to `production`
- `EB_ORIGIN` - Frontend origin URL (for CORS)
- `ENABLE_SCHEDULER` - Set to `true` or `false` (optional)

### Step 4: Deploy to AWS
```bash
# Option A: Using deploy.sh script
./deploy.sh

# Option B: Manual deployment
eb deploy
```

### Step 5: Monitor Deployment
```bash
# Check deployment status
eb status

# View logs
eb logs --all

# Stream logs in real-time
eb logs --stream

# Check health
eb health --refresh
```

---

## 🔍 Post-Deployment Verification

### 1. Check Application Logs
```bash
eb logs --all | tail -100
```

**Look for**:
- ✅ "Database connection test successful"
- ✅ "Database initialized successfully"
- ✅ No import errors
- ✅ No module not found errors
- ✅ Application started successfully
- ✅ Gunicorn workers started

**Watch for**:
- ❌ Import errors (module not found)
- ❌ Database connection errors
- ❌ Configuration errors
- ❌ Route registration errors

### 2. Test Health Endpoint
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
  "timestamp": "..."
}
```

### 3. Test Authentication Endpoint
```bash
# Test current user endpoint (should return 401 if not logged in)
curl -v http://${APP_URL}/api/user/current
```

**Expected**: HTTP 401 (Not authenticated) - this is correct

### 4. Test Login Endpoint
```bash
# Test login endpoint
curl -X POST http://${APP_URL}/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin@796!"}'
```

**Expected**: JSON response with user data

---

## 🐛 Common Deployment Issues & Solutions

### Issue 1: Module Not Found Error
**Error**: `ModuleNotFoundError: No module named 'config'`

**Solution**:
- Ensure `config.py` is in the root directory
- Ensure all module files are included in deployment
- Check that `application.py` imports are correct

### Issue 2: Database Connection Failed
**Error**: `Database connection test failed`

**Solution**:
- Verify RDS environment variables are set correctly
- Check RDS security group allows connections from EB
- Verify database credentials

### Issue 3: Import Error in Routes
**Error**: `ImportError: cannot import name 'auth_bp'`

**Solution**:
- Ensure `routes/` directory is included
- Ensure `routes/__init__.py` exists
- Check that `routes/auth.py` exports `auth_bp`

### Issue 4: Blueprint Not Registered
**Error**: Routes not accessible

**Solution**:
- Verify `application.register_blueprint(auth_bp)` is in `application.py`
- Check logs for blueprint registration messages

### Issue 5: Gunicorn Worker Timeout
**Error**: Worker timeout

**Solution**:
- Increase timeout in Procfile: `--timeout=120`
- Check for long-running operations in startup

---

## 📋 Deployment Log Analysis

### Successful Deployment Logs Should Show:

```
✅ Database connection test successful
✅ Database initialized successfully
✅ Application imports successful
✅ Blueprints registered
✅ Gunicorn started
✅ Worker processes started
```

### Error Patterns to Watch For:

```
❌ ModuleNotFoundError → Missing file in deployment
❌ ImportError → Import path issue
❌ Database connection failed → RDS configuration issue
❌ Blueprint registration failed → Route module issue
❌ Worker timeout → Startup taking too long
```

---

## 🔧 Quick Fixes

### If Deployment Fails:

1. **Check Logs Immediately**:
   ```bash
   eb logs --all | tail -200
   ```

2. **Verify Files Are Deployed**:
   ```bash
   eb ssh
   ls -la  # Check if all files are present
   ```

3. **Test Import Locally**:
   ```bash
   python -c "from application import application; print('OK')"
   ```

4. **Redeploy**:
   ```bash
   eb deploy
   ```

---

## ✅ Success Criteria

Deployment is successful when:
- ✅ Application starts without errors
- ✅ Health endpoint returns 200
- ✅ Database connection works
- ✅ Authentication endpoints work
- ✅ No errors in logs
- ✅ Frontend can connect to backend

---

## 📞 Next Steps After Deployment

1. ✅ Verify health endpoint
2. ✅ Test authentication
3. ✅ Test API endpoints
4. ✅ Check application logs
5. ✅ Monitor for errors
6. ✅ Update frontend CORS if needed
7. ✅ Run database migrations if needed

---

## 🎯 Deployment Command Summary

```bash
# 1. Navigate to backend directory
cd GaadiMech-CRM-Backend

# 2. Verify local application works
python application.py  # Test locally

# 3. Deploy
./deploy.sh
# OR
eb deploy

# 4. Monitor
eb logs --stream

# 5. Check status
eb status

# 6. Test health
curl http://$(eb status | grep CNAME | awk '{print $2}')/health
```

---

**Ready to deploy!** 🚀


