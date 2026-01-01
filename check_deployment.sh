#!/bin/bash
# Post-deployment verification script
# Checks deployment status and analyzes logs

set -e

echo "🔍 Post-Deployment Verification"
echo "=============================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if EB CLI is available
if ! command -v eb &> /dev/null; then
    echo -e "${RED}❌ EB CLI not found. Install with: pip install awsebcli${NC}"
    exit 1
fi

# Get environment status
echo -e "${BLUE}1. Checking deployment status...${NC}"
eb status

echo ""
echo -e "${BLUE}2. Checking application health...${NC}"
eb health --refresh

echo ""
echo -e "${BLUE}3. Fetching recent logs...${NC}"
echo "=============================="
RECENT_LOGS=$(eb logs --all 2>/dev/null | tail -100)

# Analyze logs for success indicators
echo ""
echo -e "${BLUE}4. Analyzing logs for success indicators...${NC}"

SUCCESS_COUNT=0
ERROR_COUNT=0

# Check for success indicators
if echo "$RECENT_LOGS" | grep -qi "Database connection test successful"; then
    echo -e "   ${GREEN}✅${NC} Database connection successful"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
else
    echo -e "   ${YELLOW}⚠️${NC}  Database connection message not found"
fi

if echo "$RECENT_LOGS" | grep -qi "Database initialized successfully"; then
    echo -e "   ${GREEN}✅${NC} Database initialized"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
else
    echo -e "   ${YELLOW}⚠️${NC}  Database initialization message not found"
fi

if echo "$RECENT_LOGS" | grep -qi "gunicorn\|worker\|started"; then
    echo -e "   ${GREEN}✅${NC} Gunicorn started"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
else
    echo -e "   ${YELLOW}⚠️${NC}  Gunicorn startup message not found"
fi

# Check for errors
if echo "$RECENT_LOGS" | grep -qi "ModuleNotFoundError\|ImportError"; then
    echo -e "   ${RED}❌${NC} Import/Module errors found"
    ERROR_COUNT=$((ERROR_COUNT + 1))
    echo "$RECENT_LOGS" | grep -i "ModuleNotFoundError\|ImportError" | head -5
fi

if echo "$RECENT_LOGS" | grep -qi "Database connection.*failed\|connection.*error"; then
    echo -e "   ${RED}❌${NC} Database connection errors found"
    ERROR_COUNT=$((ERROR_COUNT + 1))
    echo "$RECENT_LOGS" | grep -i "Database connection.*failed\|connection.*error" | head -5
fi

if echo "$RECENT_LOGS" | grep -qi "Traceback\|Exception\|Error"; then
    ERROR_LINES=$(echo "$RECENT_LOGS" | grep -i "Traceback\|Exception\|Error" | wc -l)
    if [ "$ERROR_LINES" -gt 0 ]; then
        echo -e "   ${RED}❌${NC} Found $ERROR_LINES error(s) in logs"
        ERROR_COUNT=$((ERROR_COUNT + 1))
        echo "$RECENT_LOGS" | grep -i "Traceback\|Exception\|Error" | head -10
    fi
fi

# Test health endpoint
echo ""
echo -e "${BLUE}5. Testing health endpoint...${NC}"
APP_URL=$(eb status 2>/dev/null | grep "CNAME" | awk '{print $2}' | head -n 1)

if [ -n "$APP_URL" ]; then
    echo "   Testing: http://${APP_URL}/health"
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "http://${APP_URL}/health" 2>/dev/null || echo "000")
    
    if [ "$HEALTH_RESPONSE" = "200" ]; then
        echo -e "   ${GREEN}✅${NC} Health endpoint: HTTP 200 (OK)"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        
        # Get health response
        HEALTH_BODY=$(curl -s "http://${APP_URL}/health" 2>/dev/null)
        echo "   Response: $HEALTH_BODY"
    elif [ "$HEALTH_RESPONSE" = "000" ]; then
        echo -e "   ${YELLOW}⚠️${NC}  Health endpoint: Connection failed (may still be starting)"
    else
        echo -e "   ${YELLOW}⚠️${NC}  Health endpoint: HTTP $HEALTH_RESPONSE"
    fi
else
    echo -e "   ${YELLOW}⚠️${NC}  Could not determine application URL"
fi

# Summary
echo ""
echo "=============================="
echo -e "${BLUE}Summary:${NC}"
echo "   Success indicators: $SUCCESS_COUNT"
echo "   Errors found: $ERROR_COUNT"

if [ $ERROR_COUNT -eq 0 ] && [ $SUCCESS_COUNT -ge 2 ]; then
    echo ""
    echo -e "${GREEN}✅ Deployment appears successful!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Test authentication: curl -X POST http://${APP_URL}/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"admin@796!\"}'"
    echo "2. Monitor logs: eb logs --stream"
    echo "3. Check status: eb status"
else
    echo ""
    echo -e "${YELLOW}⚠️  Please review logs for issues${NC}"
    echo ""
    echo "To view full logs:"
    echo "  eb logs --all"
    echo "  eb logs --stream"
fi

echo ""
echo "=============================="






