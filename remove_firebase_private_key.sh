#!/bin/bash
# Script to remove FIREBASE_PRIVATE_KEY from AWS Elastic Beanstalk
# This variable exceeds the 4096 character limit

set -e

ENVIRONMENT_NAME="GaadiMech-CRM-Backend-env-alb"
REGION="ap-south-1"

echo "Removing FIREBASE_PRIVATE_KEY from AWS Elastic Beanstalk..."
echo "Environment: $ENVIRONMENT_NAME"
echo "Region: $REGION"
echo ""

# Create temporary JSON file to remove the variable
TEMP_FILE=$(mktemp)
cat > "$TEMP_FILE" <<EOF
[
  {
    "Namespace": "aws:elasticbeanstalk:application:environment",
    "OptionName": "FIREBASE_PRIVATE_KEY",
    "Value": ""
  }
]
EOF

# Remove environment variable (setting to empty string removes it)
echo "Removing FIREBASE_PRIVATE_KEY..."
aws elasticbeanstalk update-environment \
  --environment-name "$ENVIRONMENT_NAME" \
  --region "$REGION" \
  --option-settings file://"$TEMP_FILE" \
  --options-to-remove \
    "Namespace=aws:elasticbeanstalk:application:environment,OptionName=FIREBASE_PRIVATE_KEY" \
  --output json > /dev/null

# Clean up
rm "$TEMP_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ FIREBASE_PRIVATE_KEY removed successfully!"
    echo ""
    echo "Note: The environment will restart automatically. This may take 2-3 minutes."
    echo ""
    echo "After restart, Firebase will use FIREBASE_SERVICE_ACCOUNT_JSON instead."
else
    echo ""
    echo "❌ Error removing environment variable"
    exit 1
fi


