#!/usr/bin/env python3
"""
Script to remove old VAPID tokens from the database
Since we're now using FCM exclusively, VAPID tokens are no longer needed
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from application import application, db
from models import PushSubscription, User
from datetime import datetime

def cleanup_vapid_tokens():
    """Remove all VAPID tokens from the database"""
    with application.app_context():
        # Get all VAPID subscriptions
        vapid_subscriptions = PushSubscription.query.filter(
            (PushSubscription.subscription_type == 'vapid') |
            ((PushSubscription.subscription_type.is_(None)) & (PushSubscription.fcm_token.is_(None))) |
            ((PushSubscription.subscription_type == '') & (PushSubscription.fcm_token.is_(None)))
        ).all()
        
        print(f"\n{'='*60}")
        print(f"VAPID Token Cleanup")
        print(f"{'='*60}")
        print(f"Found {len(vapid_subscriptions)} VAPID subscription(s) to remove\n")
        
        if len(vapid_subscriptions) == 0:
            print("✅ No VAPID tokens found. Database is clean!")
            return
        
        # Show details before deletion
        print("VAPID Subscriptions to be removed:")
        print("-" * 60)
        for sub in vapid_subscriptions:
            user = User.query.get(sub.user_id)
            user_name = user.name if user else f"Unknown (ID: {sub.user_id})"
            print(f"  ID: {sub.id}")
            print(f"    User: {user_name} (ID: {sub.user_id})")
            print(f"    Type: {sub.subscription_type or 'NULL'}")
            print(f"    Has Endpoint: {bool(sub.endpoint)}")
            print(f"    Created: {sub.created_at}")
            print(f"    Updated: {sub.updated_at}")
            print()
        
        # Confirm deletion
        response = input(f"Delete {len(vapid_subscriptions)} VAPID subscription(s)? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Cleanup cancelled")
            return
        
        # Delete VAPID subscriptions
        deleted_count = 0
        for sub in vapid_subscriptions:
            try:
                db.session.delete(sub)
                deleted_count += 1
            except Exception as e:
                print(f"❌ Error deleting subscription {sub.id}: {e}")
        
        db.session.commit()
        
        print(f"\n✅ Successfully removed {deleted_count} VAPID subscription(s)")
        print(f"{'='*60}\n")

def analyze_token_storage():
    """Analyze FCM token storage in the database"""
    with application.app_context():
        print(f"\n{'='*60}")
        print(f"FCM Token Storage Analysis")
        print(f"{'='*60}\n")
        
        # Total subscriptions
        total = PushSubscription.query.count()
        print(f"Total subscriptions: {total}")
        
        # FCM subscriptions
        fcm_subs = PushSubscription.query.filter(
            PushSubscription.fcm_token.isnot(None),
            PushSubscription.subscription_type == 'fcm'
        ).all()
        print(f"FCM subscriptions: {len(fcm_subs)}")
        
        # VAPID subscriptions
        vapid_subs = PushSubscription.query.filter(
            (PushSubscription.subscription_type == 'vapid') |
            ((PushSubscription.subscription_type.is_(None)) & (PushSubscription.fcm_token.is_(None))) |
            ((PushSubscription.subscription_type == '') & (PushSubscription.fcm_token.is_(None)))
        ).all()
        print(f"VAPID subscriptions: {len(vapid_subs)}")
        
        # Subscriptions by user
        print(f"\n--- Subscriptions by User ---")
        users = User.query.all()
        for user in users:
            user_subs = PushSubscription.query.filter_by(user_id=user.id).all()
            fcm_count = len([s for s in user_subs if s.fcm_token and s.subscription_type == 'fcm'])
            vapid_count = len([s for s in user_subs if s.subscription_type == 'vapid' or (not s.subscription_type and not s.fcm_token)])
            
            if user_subs:
                print(f"  {user.name} (ID: {user.id}, username: {user.username}):")
                print(f"    Total: {len(user_subs)}")
                print(f"    FCM: {fcm_count}")
                print(f"    VAPID: {vapid_count}")
                # Get last updated timestamp (handle None values)
                timestamps = [s.updated_at or s.created_at for s in user_subs if s.updated_at or s.created_at]
                if timestamps:
                    last_updated = max(timestamps)
                    print(f"    Last updated: {last_updated}")
                else:
                    print(f"    Last updated: N/A")
        
        # Token age analysis
        print(f"\n--- FCM Token Age Analysis ---")
        now = datetime.now()
        for sub in fcm_subs:
            updated_time = sub.updated_at or sub.created_at
            if updated_time:
                age_days = (now - updated_time).days
            else:
                age_days = 0
            user = User.query.get(sub.user_id)
            user_name = user.name if user else f"Unknown (ID: {sub.user_id})"
            print(f"  User: {user_name}")
            print(f"    Token (first 30 chars): {sub.fcm_token[:30] if sub.fcm_token else 'N/A'}...")
            print(f"    Age: {age_days} days")
            print(f"    Created: {sub.created_at}")
            print(f"    Updated: {sub.updated_at or 'N/A'}")
            print()
        
        print(f"{'='*60}\n")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Cleanup VAPID tokens and analyze FCM token storage')
    parser.add_argument('--analyze', action='store_true', help='Analyze token storage')
    parser.add_argument('--cleanup', action='store_true', help='Remove VAPID tokens')
    parser.add_argument('--all', action='store_true', help='Run both analyze and cleanup')
    
    args = parser.parse_args()
    
    if args.analyze or args.all:
        analyze_token_storage()
    
    if args.cleanup or args.all:
        cleanup_vapid_tokens()
    
    if not args.analyze and not args.cleanup and not args.all:
        print("Usage: python cleanup_vapid_tokens.py --analyze | --cleanup | --all")
        print("  --analyze: Show token storage analysis")
        print("  --cleanup: Remove VAPID tokens")
        print("  --all: Run both analyze and cleanup")

