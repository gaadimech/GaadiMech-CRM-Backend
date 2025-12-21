# Quick Deployment Guide

## 🚀 Fast Deployment Steps

### 1. Pre-Deployment Check
```bash
cd GaadiMech-CRM-Backend
./pre_deploy_check.sh
```

### 2. Deploy
```bash
./deploy.sh
# OR
eb deploy
```

### 3. Check Deployment
```bash
./check_deployment.sh
```

### 4. View Logs
```bash
eb logs --stream
```

---

## ✅ What to Look For in Logs

### Success Indicators:
- ✅ "Database connection test successful"
- ✅ "Database initialized successfully"
- ✅ "Gunicorn started"
- ✅ "Worker processes started"

### Error Indicators:
- ❌ "ModuleNotFoundError"
- ❌ "ImportError"
- ❌ "Database connection failed"
- ❌ "Traceback"

---

## 🔧 Quick Fixes

**If ModuleNotFoundError**:
- Check that all files are deployed (config.py, models.py, utils.py, routes/, services/)

**If Database Error**:
- Check environment variables: `eb printenv`
- Verify RDS security group

**If Import Error**:
- Check that routes/ and services/ directories are included

---

## 📞 Useful Commands

```bash
# Status
eb status

# Logs
eb logs --all
eb logs --stream

# Health
eb health --refresh

# Environment variables
eb printenv

# SSH into instance
eb ssh
```

---

**That's it!** 🎉



