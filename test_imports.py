#!/usr/bin/env python3
"""
Quick test script to verify all imports work correctly.
"""
import sys

print("Testing imports...")
print("=" * 50)

try:
    print("1. Testing config imports...")
    from config import application, db, login_manager, limiter, ist
    print("   ✅ Config imports successful")
except Exception as e:
    print(f"   ❌ Config import failed: {e}")
    sys.exit(1)

try:
    print("2. Testing models imports...")
    from models import User, Lead
    print("   ✅ Models imports successful")
except Exception as e:
    print(f"   ❌ Models import failed: {e}")
    sys.exit(1)

try:
    print("3. Testing utils imports...")
    from utils import normalize_mobile_number
    print("   ✅ Utils imports successful")
except Exception as e:
    print(f"   ❌ Utils import failed: {e}")
    sys.exit(1)

try:
    print("4. Testing routes imports...")
    from routes.auth import auth_bp
    print("   ✅ Routes imports successful")
except Exception as e:
    print(f"   ❌ Routes import failed: {e}")
    sys.exit(1)

try:
    print("5. Testing services imports...")
    from services.database import init_database
    print("   ✅ Services imports successful")
except Exception as e:
    print(f"   ❌ Services import failed: {e}")
    sys.exit(1)

try:
    print("6. Testing full application import...")
    # Import application module (this will execute all the code)
    import application
    print("   ✅ Full application import successful")
    print(f"   ✅ Flask app: {application.application}")
except Exception as e:
    print(f"   ❌ Full application import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 50)
print("✅ All imports successful! Application should run correctly.")
print("=" * 50)

