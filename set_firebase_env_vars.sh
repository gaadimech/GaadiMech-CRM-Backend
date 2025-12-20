#!/bin/bash
# Script to set Firebase environment variables in AWS Elastic Beanstalk
# This script properly handles multi-line private keys

set -e

ENVIRONMENT_NAME="GaadiMech-CRM-Backend-env-alb"
REGION="ap-south-1"

# Firebase credentials (replace with your actual values)
FIREBASE_PROJECT_ID="gaadimech-crm"
FIREBASE_CLIENT_EMAIL="firebase-adminsdk-fbsvc@gaadimech-crm.iam.gserviceaccount.com"

# Firebase Private Key - IMPORTANT: Use actual newlines, not \n
# Copy the entire key from your Firebase service account JSON file
# Make sure it includes -----BEGIN PRIVATE KEY----- and -----END PRIVATE KEY-----
FIREBASE_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDQtTrTvo+JnCjF
RpxvY8beKGQbTK1YsstDxCqbbIZxLrNRCXCgYHY5MI97WMfDvUf3wiri6QTJevGb
xLq5aA4n5NeNGBxs7NTauECSoUDAinbz64RKASIiCJS8UwJB+p4o11c1V7x1bRxz
R5TxvUUFXbZa7KZUPChOBX5JeScLea50TeDOpwn2/mo64s1Kk/1EIT/+RVS0olQ+
/rLdN15rI+MQK3KKzGfkpwaHtvCBJux5bWHlT/I7LiSqvrkQqPrKtH1JDwa4bz+Y
m2RoC+YC1D9x/aprEHJQUD45jPYXqAkNGTS8XktY3SoR8dCFGkOmBWKvma6twyql
WJ8M2QdbAgMBAAECggEARhgfxj6xYXOfY8YXwvddMn6ZRGvnqir+RmerMaDstDWN
htFnUI2lFwb+oVwLV2uKMKU3FxdQgsR2Qaz8U0mlu3NJi3sGDPUrdbu9ACIFJ8U5
Nympt9sSliCQp4EveG5N0QSlpuYtBrka/YKUfO3msOss0/O31wGPPcjthYqZeOoM
m9WP4U/VFAEjXraE6u92zsjs1gKJfRzzb9dh8Oln/nlcTTVza3xLByGOA8s0y4eO
JCFMqnhGCNuq2LWotTA7D+a8xcUuHutW+mrWXbpGS7fyZ0PWDOGSkstBu7sX95iz
Oei46PIInPeHHAj3HoxlA5cSPd3IcWeeMrX1v53BGQKBgQD+P+BjgqvUxEpw9kDh
BIU+WHFPDP4MmVDboyLQxb9AEH5vJQsh4dSclRHox/KoYmX6fZ/C/TC3g51PYP/P
jV6vsPX04PTh4Nwu03iX+WqDhRXk5iaodqb/3IgdKkIsvSlYw8Csf05I4RE12weV
bZRacOChzoobeK/yFUUe0vU4cwKBgQDSJRWsn8Fr4Fw0B1hhOlLP8f0L1umxwOIx
V+tsqd+0JJUIX5Opg61VZIvK26kg6PCN0p0GFJ3KPWA7PsWivzf7ydxA3A/XHLnW
iBaDXF5PP4KU30+52lEWPSpZ3WFpd4SDDBTEcYegRN0dRUK9UO1C+u4sB1rhhW6B
Ej8TgZgDeQKBgQCu5gwbCDniLIG1AYGSCUULpVWU9rAQxKr93FRH37B3hqEjHg1x
amOSr21Zf6pqsP3L+f0b6oZHx49Ams5+3ZYkMAySPunWNJPi1nBfwyDFhpiQFM7F
FpI88lzkCzzof9vghxCU2SJmOgVX0et+nJnwOTQduvIAgd4vHvikgqRUBwKBgEyv
AbDDf0aJUbwerg6UxOFi8a8fVpnpw+Czr5IwjxRigQvULMMf7OGLVkPJUndS6W0n
XOt6HHZPXU1hQ6d21cwIxlnYs+MQdXQmpuh6jWOnzlPbBXHRi+NsoIa4dTKSTYWw
o+dnclF2r6Vdv9PrsxjNDpp8eJpxIXjyGphYowspAoGAAmAmWpo+dVcRH+V1JslN
aGGR065TijXG8N1ppDK4DcMVuS4QB5uS4RqPS1aDmCur+n4UPu7A7o3Djr29zxy0
0qpH6pnHfqGvdgRrufgsrhCt17NQxMOh7nvMWSthWlN8EpbSGYJ+o02nrcoV2qDa
y/yPfOp+39436sTnErzSRqg=
-----END PRIVATE KEY-----'

echo "Setting Firebase environment variables in AWS Elastic Beanstalk..."
echo "Environment: $ENVIRONMENT_NAME"
echo "Region: $REGION"
echo ""

# Set environment variables using AWS CLI
# Note: For multi-line values, we need to use a different approach
# AWS CLI doesn't handle multi-line values well, so we'll use a JSON file

# Create temporary JSON file with environment variables
TEMP_FILE=$(mktemp)
cat > "$TEMP_FILE" <<EOF
[
  {
    "Namespace": "aws:elasticbeanstalk:application:environment",
    "OptionName": "FIREBASE_PROJECT_ID",
    "Value": "$FIREBASE_PROJECT_ID"
  },
  {
    "Namespace": "aws:elasticbeanstalk:application:environment",
    "OptionName": "FIREBASE_CLIENT_EMAIL",
    "Value": "$FIREBASE_CLIENT_EMAIL"
  },
  {
    "Namespace": "aws:elasticbeanstalk:application:environment",
    "OptionName": "FIREBASE_PRIVATE_KEY",
    "Value": $(echo "$FIREBASE_PRIVATE_KEY" | jq -Rs .)
  }
]
EOF

echo "Updating environment variables..."
aws elasticbeanstalk update-environment \
  --environment-name "$ENVIRONMENT_NAME" \
  --region "$REGION" \
  --option-settings file://"$TEMP_FILE"

# Clean up
rm "$TEMP_FILE"

echo ""
echo "✅ Firebase environment variables updated successfully!"
echo ""
echo "Note: The environment will restart automatically. This may take a few minutes."
echo "You can check the status with:"
echo "  aws elasticbeanstalk describe-environments --environment-names $ENVIRONMENT_NAME --region $REGION"

