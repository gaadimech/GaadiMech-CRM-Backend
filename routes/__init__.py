"""
Routes package for the CRM application.
All route handlers are organized into separate modules here.
"""
# Import only existing route modules
from .auth import auth_bp

# TODO: Import other route modules as they are created
# from .leads import leads_bp
# from .admin import admin_bp
# from .whatsapp import whatsapp_bp
# from .dashboard import dashboard_bp
# from .followups import followups_bp
# from .push_notifications import push_bp

__all__ = ['auth_bp']  # Add other blueprints as they are created

