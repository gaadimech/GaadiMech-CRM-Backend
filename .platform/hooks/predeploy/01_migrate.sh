#!/bin/bash
# Run database migrations before deployment
cd /var/app/ondeck
source /var/app/venv/*/bin/activate
flask db upgrade || echo "Migration failed, continuing deployment"


