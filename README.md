# GaadiMech CRM - Backend

Flask backend API server for the GaadiMech CRM application, configured for AWS Elastic Beanstalk deployment.

## Local Development Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   Create a `.env` file in this directory (see `.env.example` for reference):
   ```
   RDS_HOST=your-rds-endpoint.region.rds.amazonaws.com
   RDS_DB=your_database_name
   RDS_USER=your_database_user
   RDS_PASSWORD=your_secure_password
   RDS_PORT=5432
   SECRET_KEY=your-super-secret-key
   FLASK_ENV=development
   PORT=5000
   ```

3. **Run database migrations:**
   ```bash
   flask db upgrade
   ```

4. **Run locally:**
   ```bash
   python run_local.py
   ```
   The server will start on `http://localhost:5000`

## AWS Elastic Beanstalk Deployment

### Prerequisites
- AWS CLI installed and configured
- EB CLI installed (`pip install awsebcli`)
- AWS RDS PostgreSQL database instance
- AWS account with appropriate permissions

### Initial Setup

1. **Initialize EB application:**
   ```bash
   eb init -p python-3.11 GaadiMech-CRM-Backend --region ap-south-1
   ```

2. **Create environment:**
   ```bash
   eb create GaadiMech-CRM-Backend-env
   ```

3. **Configure environment variables in AWS Console:**
   - Go to Elastic Beanstalk → Your Environment → Configuration → Software
   - Add the following environment properties:
     - `RDS_HOST`: Your RDS endpoint
     - `RDS_DB`: Database name
     - `RDS_USER`: Database username
     - `RDS_PASSWORD`: Database password
     - `RDS_PORT`: 5432
     - `SECRET_KEY`: Your secret key
     - `FLASK_ENV`: production
     - `EB_ORIGIN`: Your Railway frontend URL (e.g., https://your-app.railway.app)

### Deployment Methods

#### Option 1: Using EB CLI (Recommended)
```bash
# Deploy to existing environment
eb deploy

# Or deploy to specific environment
eb deploy GaadiMech-CRM-Backend-env
```

#### Option 2: Using AWS CLI (Create ZIP)
```bash
# Create deployment package (excludes files in .ebignore)
zip -r ../GaadiMech-CRM-Backend.zip . -x "*.git*" -x "*__pycache__*" -x "*.env*" -x "*.db"

# Upload using AWS CLI
aws elasticbeanstalk create-application-version \
  --application-name GaadiMech-CRM-Backend \
  --version-label v1.0.0 \
  --source-bundle S3Bucket=your-bucket,S3Key=GaadiMech-CRM-Backend.zip

aws elasticbeanstalk update-environment \
  --environment-name GaadiMech-CRM-Backend-env \
  --version-label v1.0.0
```

#### Option 3: Manual ZIP Upload
1. Create a ZIP file excluding files in `.ebignore`
2. Go to AWS Elastic Beanstalk Console
3. Upload and deploy the ZIP file

### Post-Deployment

1. **Run migrations:**
   The pre-deploy hook will automatically run migrations, but you can also run manually:
   ```bash
   eb ssh
   cd /var/app/current
   source /var/app/venv/*/bin/activate
   flask db upgrade
   ```

2. **Check logs:**
   ```bash
   eb logs
   ```

3. **Open application:**
   ```bash
   eb open
   ```

### Configuration Files

- `.ebextensions/01_python.config`: Python and WSGI configuration
- `.ebextensions/02_database.config`: Database environment variables
- `.ebextensions/03_nginx.config`: Nginx proxy settings
- `.platform/hooks/predeploy/01_migrate.sh`: Pre-deployment migration hook
- `.ebignore`: Files to exclude from deployment package
- `Procfile`: Process definition for gunicorn

### API Endpoints

- `POST /login` - User login
- `GET /api/user/current` - Get current user info
- `GET /api/leads` - Get leads list
- `POST /api/leads` - Create new lead
- And more...

### CORS Configuration

The backend is configured to accept requests from:
- Local development: `http://localhost:3000`
- Production: Your Railway frontend URL (set via `EB_ORIGIN` environment variable)

### Troubleshooting

- **Database connection issues:** Verify RDS security groups allow connections from EB environment
- **Migration failures:** Check logs with `eb logs` and run migrations manually if needed
- **CORS errors:** Ensure `EB_ORIGIN` is set correctly to your Railway frontend URL
