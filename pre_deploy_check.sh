#!/bin/bash
# Pre-deployment verification script
# Checks that all required files and modules are ready for deployment

set -e

echo "🔍 Pre-Deployment Verification"
echo "=============================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0

# Check 1: Required files exist
echo "1. Checking required files..."
REQUIRED_FILES=(
    "application.py"
    "config.py"
    "models.py"
    "utils.py"
    "Procfile"
    "requirements.txt"
    "runtime.txt"
    "routes/__init__.py"
    "routes/auth.py"
    "routes/common.py"
    "services/__init__.py"
    "services/database.py"
    "services/firebase_notifications.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "   ${GREEN}✅${NC} $file"
    else
        echo -e "   ${RED}❌${NC} $file - MISSING"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check 2: Python can import application
echo ""
echo "2. Checking Python imports..."
if python3 -c "from application import application" 2>/dev/null; then
    echo -e "   ${GREEN}✅${NC} Application import successful"
else
    echo -e "   ${RED}❌${NC} Application import failed"
    ERRORS=$((ERRORS + 1))
fi

# Check 3: All modules can be imported
echo ""
echo "3. Checking module imports..."
if python3 -c "
from config import application, db, login_manager, limiter, ist
from models import User, Lead
from utils import normalize_mobile_number
from routes.auth import auth_bp
from services.database import init_database
from services.firebase_notifications import initialize_firebase, send_fcm_notification
" 2>/dev/null; then
    echo -e "   ${GREEN}✅${NC} All module imports successful"
else
    echo -e "   ${RED}❌${NC} Module imports failed"
    ERRORS=$((ERRORS + 1))
fi

# Check 4: Procfile format
echo ""
echo "4. Checking Procfile..."
if grep -q "application:application" Procfile 2>/dev/null; then
    echo -e "   ${GREEN}✅${NC} Procfile format correct"
else
    echo -e "   ${RED}❌${NC} Procfile format incorrect"
    ERRORS=$((ERRORS + 1))
fi

# Check 5: Gunicorn in requirements
echo ""
echo "5. Checking requirements.txt..."
if grep -q "gunicorn" requirements.txt 2>/dev/null; then
    echo -e "   ${GREEN}✅${NC} Gunicorn in requirements"
else
    echo -e "   ${RED}❌${NC} Gunicorn not in requirements"
    ERRORS=$((ERRORS + 1))
fi

# Check 6: Runtime version
echo ""
echo "6. Checking runtime.txt..."
if [ -f "runtime.txt" ]; then
    RUNTIME=$(cat runtime.txt)
    echo -e "   ${GREEN}✅${NC} Runtime: $RUNTIME"
else
    echo -e "   ${YELLOW}⚠️${NC}  runtime.txt not found (optional)"
fi

# Summary
echo ""
echo "=============================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    echo -e "${GREEN}Ready for deployment!${NC}"
    exit 0
else
    echo -e "${RED}❌ $ERRORS ERROR(S) FOUND${NC}"
    echo -e "${RED}Please fix errors before deploying${NC}"
    exit 1
fi


