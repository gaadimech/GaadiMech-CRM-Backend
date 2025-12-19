"""
Common route utilities and helper functions.
"""
import os
from flask import send_file, render_template

def serve_frontend():
    """Serve the Next.js index.html for client-side routing"""
    try:
        frontend_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'frontend')
        index_path = os.path.join(frontend_path, 'index.html')

        if os.path.exists(index_path):
            return send_file(index_path)
        else:
            return render_template('error.html', error="Frontend not built. Please build the Next.js application."), 404
    except Exception as e:
        print(f"Error serving frontend: {e}")
        return render_template('error.html', error="Error loading frontend application."), 500

