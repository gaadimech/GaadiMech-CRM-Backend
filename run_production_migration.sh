#!/bin/bash
# Script to run database migrations on production
# Usage: ./run_production_migration.sh

echo "🔧 Setting up SSH for Elastic Beanstalk..."
eb ssh --setup

echo ""
echo "📦 Running database migrations on production..."
eb ssh --command "cd /var/app/current && source /var/app/venv/*/bin/activate && flask db upgrade"

echo ""
echo "✅ Migration complete! Verifying..."
eb ssh --command "cd /var/app/current && source /var/app/venv/*/bin/activate && flask db current"

echo ""
echo "🎉 Done! The processed_count column should now exist."

