#!/usr/bin/env python3
"""
Script to fix admin user's is_admin field in the database.
Run this if admin features are not showing up.
"""
import os
from dotenv import load_dotenv
from application import application, db, User

load_dotenv()

def fix_admin_role():
    """Ensure admin user has is_admin=True"""
    with application.app_context():
        admin_user = User.query.filter_by(username='admin').first()
        
        if not admin_user:
            print("❌ Admin user not found!")
            print("Creating admin user...")
            admin_user = User(
                username='admin',
                name='Administrator',
                is_admin=True
            )
            admin_user.set_password('admin@796!')
            db.session.add(admin_user)
            db.session.commit()
            print("✅ Admin user created with is_admin=True")
        else:
            print(f"✅ Admin user found: {admin_user.username}")
            print(f"   Current is_admin value: {admin_user.is_admin}")
            print(f"   Type: {type(admin_user.is_admin)}")
            
            if not admin_user.is_admin:
                print("⚠️  Admin user's is_admin is False! Fixing...")
                admin_user.is_admin = True
                db.session.commit()
                print("✅ Admin user's is_admin field updated to True")
            else:
                print("✅ Admin user already has is_admin=True")
        
        # Verify
        admin_user = User.query.filter_by(username='admin').first()
        print(f"\n📊 Verification:")
        print(f"   Username: {admin_user.username}")
        print(f"   Name: {admin_user.name}")
        print(f"   is_admin: {admin_user.is_admin}")
        print(f"   Type: {type(admin_user.is_admin)}")

if __name__ == '__main__':
    try:
        fix_admin_role()
        print("\n✅ Script completed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
