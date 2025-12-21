#!/bin/bash
# Script to set FIREBASE_SERVICE_ACCOUNT_JSON in AWS Elastic Beanstalk
# This avoids the 4096 character limit issue

set -e

ENVIRONMENT_NAME="GaadiMech-CRM-Backend-env-alb"
REGION="ap-south-1"
FIREBASE_JSON_FILE="../gaadimech-crm-firebase-adminsdk-fbsvc-d239efed44.json"

echo "Setting FIREBASE_SERVICE_ACCOUNT_JSON in AWS Elastic Beanstalk..."
echo "Environment: $ENVIRONMENT_NAME"
echo "Region: $REGION"
echo ""

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "❌ Error: jq is not installed"
    echo "   Install with: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
fi

# Check if Firebase JSON file exists
if [ ! -f "$FIREBASE_JSON_FILE" ]; then
    echo "❌ Error: Firebase JSON file not found: $FIREBASE_JSON_FILE"
    exit 1
fi

# Convert JSON to single-line compact format, then base64-encode it
# This avoids any escape sequence issues with newlines
echo "Converting JSON to single-line format and base64-encoding..."
FIREBASE_JSON=$(cat "$FIREBASE_JSON_FILE" | jq -c .)
FIREBASE_JSON_B64=$(echo -n "$FIREBASE_JSON" | base64)

# Check length
JSON_LENGTH=${#FIREBASE_JSON_B64}
echo "Base64-encoded JSON length: $JSON_LENGTH characters"
if [ $JSON_LENGTH -gt 4096 ]; then
    echo "❌ Error: Base64-encoded JSON string exceeds 4096 character limit!"
    exit 1
fi
echo "✅ Base64-encoded JSON length is within AWS limit (4096)"
echo ""

# Update environment variable directly with base64-encoded JSON
echo "Updating environment variable..."
aws elasticbeanstalk update-environment \
  --environment-name "$ENVIRONMENT_NAME" \
  --region "$REGION" \
  --option-settings \
    "Namespace=aws:elasticbeanstalk:application:environment,OptionName=FIREBASE_SERVICE_ACCOUNT_JSON,Value=$FIREBASE_JSON_B64" \
  --output json > /dev/null

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Firebase environment variable updated successfully!"
    echo ""
    echo "Note: The environment will restart automatically. This may take 2-3 minutes."
    echo ""
    echo "To verify, check CloudWatch logs for:"
    echo "  ✅ Firebase initialized from JSON string"
    echo ""
    echo "You can also check status with:"
    echo "  aws elasticbeanstalk describe-environments --environment-names $ENVIRONMENT_NAME --region $REGION --query 'Environments[0].Status'"
else
    echo ""
    echo "❌ Error updating environment variable"
    exit 1
fi

