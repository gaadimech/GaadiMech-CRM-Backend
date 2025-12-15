# Production Migration Fix - processed_count Column Missing

## Issue
Production database is missing the `processed_count` column in `whatsapp_bulk_job` table, causing 500 errors.

## Root Cause
The migration `0938d34e5593_add_processed_count_to_bulk_job.py` was created and applied locally, but hasn't been run on production.

## Solution

### Option 1: Run Migration via SSH (Recommended)

1. **Set up SSH access:**
   ```bash
   cd GaadiMech-CRM-Backend
   eb ssh --setup
   ```

2. **Run the migration:**
   ```bash
   eb ssh --command "cd /var/app/current && source /var/app/venv/*/bin/activate && flask db upgrade"
   ```

3. **Verify:**
   ```bash
   eb ssh --command "cd /var/app/current && source /var/app/venv/*/bin/activate && flask db current"
   ```

### Option 2: Use the Automated Script

```bash
cd GaadiMech-CRM-Backend
./run_production_migration.sh
```

### Option 3: Redeploy (Migrations should run automatically)

The pre-deploy hook (`.platform/hooks/predeploy/01_migrate.sh`) should run migrations automatically, but it may have failed silently. To force a redeploy:

```bash
cd GaadiMech-CRM-Backend
eb deploy
```

Then check logs:
```bash
eb logs --all | grep -i migration
```

## Migrations That Need to Run

1. ✅ `0938d34e5593_add_processed_count_to_bulk_job.py` - **REQUIRED** (fixes current error)
2. ✅ `9eac0271d6e2_add_whatsapp_business_id_to_template_.py` - **RECOMMENDED** (for per-template bot ID tracking)

## Verification

After running migrations, verify the column exists:

```bash
eb ssh --command "cd /var/app/current && source /var/app/venv/*/bin/activate && python -c \"from application import db; from sqlalchemy import inspect; inspector = inspect(db.engine); cols = [c['name'] for c in inspector.get_columns('whatsapp_bulk_job')]; print('processed_count' in cols)\""
```

Should output: `True`

## Quick Fix (If SSH Setup Fails)

If SSH setup doesn't work, you can temporarily add the column directly via SQL:

```bash
eb ssh --command "cd /var/app/current && source /var/app/venv/*/bin/activate && python -c \"from application import db; db.engine.execute('ALTER TABLE whatsapp_bulk_job ADD COLUMN IF NOT EXISTS processed_count INTEGER DEFAULT 0'); print('Column added')\""
```

## After Fix

1. Refresh the page - the error should be gone
2. The progress bar should work correctly
3. Consider re-syncing templates to populate `whatsapp_business_id` column

