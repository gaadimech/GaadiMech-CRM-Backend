#!/bin/bash
# Test script for backend

echo "🧪 Testing Backend Setup..."
echo "================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please create .env file with database credentials"
    exit 1
fi
echo "✅ .env file exists"

# Check if Python dependencies are installed
echo ""
echo "Checking Python dependencies..."
python3 -c "import flask" 2>/dev/null && echo "✅ Flask installed" || echo "❌ Flask not installed - run: pip install -r requirements.txt"
python3 -c "import flask_sqlalchemy" 2>/dev/null && echo "✅ Flask-SQLAlchemy installed" || echo "❌ Flask-SQLAlchemy not installed"
python3 -c "import flask_login" 2>/dev/null && echo "✅ Flask-Login installed" || echo "❌ Flask-Login not installed"
python3 -c "import flask_cors" 2>/dev/null && echo "✅ Flask-CORS installed" || echo "❌ Flask-CORS not installed"

# Test application import
echo ""
echo "Testing application import..."
python3 -c "from application import application; print('✅ Application imports successfully')" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Backend is ready to run!"
    echo ""
    echo "To start the backend server, run:"
    echo "  python3 run_local.py"
else
    echo "❌ Backend has import errors. Please install dependencies:"
    echo "  pip install -r requirements.txt"
fi

