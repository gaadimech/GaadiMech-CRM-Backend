"""
Authentication routes.
Handles login, logout, and user session management.
"""
from flask import Blueprint, request, jsonify, make_response, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from config import db, limiter
from models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST', 'OPTIONS'])
@limiter.limit("20 per minute", methods=['POST'])
def login():
    """Handle user login"""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept, X-Requested-With, Origin')
        return response

    # For GET requests, always serve Next.js frontend
    if request.method == 'GET':
        from routes.common import serve_frontend
        return serve_frontend()

    # For POST requests, handle as API login
    try:
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            return jsonify({
                'success': True,
                'message': 'Already logged in',
                'user': {
                    'id': current_user.id,
                    'username': current_user.username,
                    'name': current_user.name,
                    'is_admin': current_user.is_admin
                }
            })
    except Exception:
        pass

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            username = data.get('username', '')
            password = data.get('password', '')
        else:
            username = request.form.get('username', '')
            password = request.form.get('password', '')

        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required'}), 400

        try:
            user = User.query.filter_by(username=username).first()

            if not user:
                return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

            if not user.check_password(password):
                return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

            login_user(user, remember=True)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'name': user.name,
                    'is_admin': user.is_admin
                }
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            db.session.rollback()
            error_msg = f'An error occurred during login: {str(e)}' if current_app.debug else 'An error occurred during login. Please try again.'
            return jsonify({'success': False, 'message': error_msg}), 500

    from routes.common import serve_frontend
    return serve_frontend()


@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    logout_user()
    accept_header = request.headers.get('Accept', '')
    if 'application/json' in accept_header:
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    return redirect(url_for('auth.login'))


@auth_bp.route('/api/user/current', methods=['GET', 'OPTIONS'])
def api_user_current():
    """Get current user information"""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = make_response()
        origin = request.headers.get('Origin', '*')
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept, X-Requested-With, Origin')
        return response

    # Debug logging
    print(f"[DEBUG] /api/user/current called from origin: {request.headers.get('Origin')}")
    print(f"[DEBUG] Request method: {request.method}")
    print(f"[DEBUG] Has session cookie: {request.cookies.get('session') is not None}")

    try:
        # Check if user is authenticated without redirecting
        # Handle case where database connection might fail
        try:
            if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
                response = jsonify({'error': 'Not authenticated'})
                response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
                response.headers.add('Access-Control-Allow-Credentials', 'true')
                return response, 401

            response = jsonify({
                'id': current_user.id,
                'username': current_user.username,
                'name': current_user.name,
                'is_admin': current_user.is_admin
            })
            # Add CORS headers
            response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            return response
        except Exception as db_error:
            # If database connection fails, return 503 (Service Unavailable) instead of 401
            # This prevents redirect loops when DB is down
            print(f"Database error in api_user_current: {db_error}")
            import traceback
            traceback.print_exc()
            error_response = jsonify({'error': 'Database connection failed', 'message': 'Service temporarily unavailable'})
            error_response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
            error_response.headers.add('Access-Control-Allow-Credentials', 'true')
            return error_response, 503
    except Exception as e:
        print(f"Error in api_user_current: {e}")
        import traceback
        traceback.print_exc()
        error_response = jsonify({'error': str(e)})
        error_response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        error_response.headers.add('Access-Control-Allow-Credentials', 'true')
        return error_response, 500

