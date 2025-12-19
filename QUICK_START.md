# Quick Start Guide - Running the Application

## 🚀 How to Run the Application Locally

### Step 1: Navigate to Backend Directory
```bash
cd GaadiMech-CRM-Backend
```

### Step 2: Activate Virtual Environment (if using one)
```bash
source venv/bin/activate  # On Mac/Linux
# OR
venv\Scripts\activate     # On Windows
```

### Step 3: Run the Application

**Option A: Using run_local.py (Recommended for Development)**
```bash
python run_local.py
```

**Option B: Direct Python**
```bash
python application.py
```

**Option C: Using Flask CLI**
```bash
export FLASK_APP=application.py
flask run
```

### Step 4: Access the Application
- **Frontend**: http://localhost:5000
- **API**: http://localhost:5000/api/...
- **Health Check**: http://localhost:5000/health

---

## 📋 What Happens When You Run

1. **`application.py`** is executed
2. It imports from:
   - `config.py` → Sets up Flask app, database, CORS
   - `models.py` → Loads all database models
   - `utils.py` → Loads utility functions
   - `routes/auth.py` → Loads authentication routes
   - `services/database.py` → Initializes database
3. Database connection is tested
4. Default users are created (if they don't exist)
5. Flask server starts on port 5000

---

## 🔍 Understanding the File Flow

```
START: run_local.py or application.py
    ↓
    ├─→ config.py (creates Flask app, database connection)
    │   └─→ Returns: application, db, login_manager, limiter
    │
    ├─→ models.py (defines database tables)
    │   └─→ Returns: User, Lead, etc.
    │
    ├─→ utils.py (helper functions)
    │   └─→ Returns: normalize_mobile_number, etc.
    │
    ├─→ routes/auth.py (authentication endpoints)
    │   └─→ Returns: auth_bp (blueprint)
    │
    └─→ services/database.py (database setup)
        └─→ init_database() function

application.py registers everything and starts server
```

---

## 🎯 File Purpose Summary

| File | Purpose | When to Edit |
|------|---------|--------------|
| **application.py** | Main entry point - runs the server | Register new blueprints, add app-level handlers |
| **config.py** | Flask configuration & setup | Change database, CORS, session settings |
| **models.py** | Database table definitions | Add/modify database tables |
| **utils.py** | Helper functions | Add utility functions |
| **routes/auth.py** | Login/logout endpoints | Modify authentication |
| **services/database.py** | Database initialization | Modify startup data |

---

## ✅ Testing Checklist

After running, verify:
- [ ] Server starts without errors
- [ ] Can access http://localhost:5000
- [ ] Health check works: http://localhost:5000/health
- [ ] Login works: http://localhost:5000/login
- [ ] Database connection is successful (check console output)

---

## 🐛 Common Issues

### Issue: Import Errors
**Solution**: Make sure you're in the `GaadiMech-CRM-Backend` directory

### Issue: Database Connection Failed
**Solution**: Check your `.env` file or `run_local.py` has correct database credentials

### Issue: Port Already in Use
**Solution**: 
```bash
# Find and kill process on port 5000
lsof -ti:5000 | xargs kill -9  # Mac/Linux
# OR change port in run_local.py
```

### Issue: Module Not Found
**Solution**: 
```bash
# Install dependencies
pip install -r requirements.txt
```

---

## 📝 Next Steps After Running

1. **Test the API**: Use Postman or curl to test endpoints
2. **Check the logs**: Watch console for any errors
3. **Access the frontend**: Open http://localhost:5000 in browser
4. **Test login**: Try logging in with default credentials

---

## 🔑 Default Credentials

Created automatically on first run:
- **Admin**: username: `admin`, password: `admin@796!`
- **User 1**: username: `hemlata`, password: `hemlata123`
- **User 2**: username: `sneha`, password: `sneha123`

---

That's it! The application should now be running. 🎉

