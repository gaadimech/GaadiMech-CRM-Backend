#!/usr/bin/env python3
import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

# Database connection parameters
DB_PARAMS = {
    'host': os.getenv('RDS_HOST', 'crm-portal-db.cnewyw0y0leb.ap-south-1.rds.amazonaws.com'),
    'database': os.getenv('RDS_DB', 'crmportal'),
    'user': os.getenv('RDS_USER', 'crmadmin'),
    'password': os.getenv('RDS_PASSWORD', 'GaadiMech2024!'),
    'port': os.getenv('RDS_PORT', '5432')
}

def check_overdue_leads():
    """Check leads with followup dates before August 24th, 2025"""
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        # Set target date (August 24th, 2025)
        target_date = datetime(2025, 8, 24)
        ist = pytz.timezone('Asia/Kolkata')
        target_date_ist = ist.localize(target_date)
        
        print(f"Checking leads with followup dates before: {target_date_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print("=" * 70)
        
        # Query 1: Total count of overdue leads
        cur.execute("""
            SELECT COUNT(*) as total_overdue
            FROM lead 
            WHERE followup_date < %s
        """, (target_date_ist,))
        
        total_overdue = cur.fetchone()[0]
        print(f"📊 Total overdue leads: {total_overdue}")
        print()
        
        # Query 2: Overdue leads grouped by user
        cur.execute("""
            SELECT 
                u.name as user_name,
                u.id as user_id,
                COUNT(l.id) as overdue_count,
                COUNT(CASE WHEN l.status = 'Needs Followup' THEN 1 END) as needs_followup,
                COUNT(CASE WHEN l.status = 'Did Not Pick Up' THEN 1 END) as did_not_pick_up,
                COUNT(CASE WHEN l.status = 'Confirmed' THEN 1 END) as confirmed,
                COUNT(CASE WHEN l.status = 'Open' THEN 1 END) as open_status,
                COUNT(CASE WHEN l.status = 'Completed' THEN 1 END) as completed,
                COUNT(CASE WHEN l.status = 'Feedback' THEN 1 END) as feedback
            FROM lead l
            JOIN "user" u ON l.creator_id = u.id
            WHERE l.followup_date < %s
            GROUP BY u.id, u.name
            ORDER BY overdue_count DESC
        """, (target_date_ist,))
        
        user_results = cur.fetchall()
        
        print("👥 Overdue leads by user:")
        print("-" * 70)
        print(f"{'User Name':<20} {'User ID':<8} {'Total':<6} {'Needs':<6} {'No Pick':<6} {'Conf':<6} {'Open':<6} {'Comp':<6} {'Feed':<6}")
        print("-" * 70)
        
        for user_name, user_id, total, needs_followup, did_not_pick_up, confirmed, open_status, completed, feedback in user_results:
            print(f"{user_name:<20} {user_id:<8} {total:<6} {needs_followup:<6} {did_not_pick_up:<6} {confirmed:<6} {open_status:<6} {completed:<6} {feedback:<6}")
        
        print("-" * 70)
        
        # Query 3: Status breakdown for all overdue leads
        cur.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM lead 
            WHERE followup_date < %s
            GROUP BY status
            ORDER BY count DESC
        """, (target_date_ist,))
        
        status_results = cur.fetchall()
        
        print("\n📈 Status breakdown for overdue leads:")
        print("-" * 40)
        for status, count in status_results:
            print(f"{status:<20} {count}")
        
        # Query 4: Date range breakdown
        cur.execute("""
            SELECT 
                'Over 30 days overdue' as overdue_range,
                COUNT(*) as count
            FROM lead 
            WHERE followup_date < %s - INTERVAL '30 days'
            UNION ALL
            SELECT 
                '7-30 days overdue' as overdue_range,
                COUNT(*) as count
            FROM lead 
            WHERE followup_date >= %s - INTERVAL '30 days' AND followup_date < %s - INTERVAL '7 days'
            UNION ALL
            SELECT 
                '1-7 days overdue' as overdue_range,
                COUNT(*) as count
            FROM lead 
            WHERE followup_date >= %s - INTERVAL '7 days' AND followup_date < %s - INTERVAL '1 day'
            UNION ALL
            SELECT 
                'Today' as overdue_range,
                COUNT(*) as count
            FROM lead 
            WHERE followup_date >= %s - INTERVAL '1 day' AND followup_date < %s
        """, (target_date_ist, target_date_ist, target_date_ist, target_date_ist, target_date_ist, target_date_ist, target_date_ist))
        
        range_results = cur.fetchall()
        
        print("\n📅 Overdue by time range:")
        print("-" * 40)
        for overdue_range, count in range_results:
            print(f"{overdue_range:<25} {count}")
        
        # Query 5: Sample of oldest overdue leads
        cur.execute("""
            SELECT 
                l.id,
                l.customer_name,
                l.mobile,
                l.followup_date,
                l.status,
                u.name as user_name
            FROM lead l
            JOIN "user" u ON l.creator_id = u.id
            WHERE l.followup_date < %s
            ORDER BY l.followup_date ASC
            LIMIT 10
        """, (target_date_ist,))
        
        oldest_leads = cur.fetchall()
        
        print(f"\n🔍 Top 10 oldest overdue leads:")
        print("-" * 80)
        print(f"{'Lead ID':<8} {'Customer':<20} {'Mobile':<15} {'Followup Date':<20} {'Status':<15} {'User':<15}")
        print("-" * 80)
        
        for lead_id, customer_name, mobile, followup_date, status, user_name in oldest_leads:
            followup_str = followup_date.strftime('%Y-%m-%d %H:%M')
            print(f"{lead_id:<8} {customer_name:<20} {mobile:<15} {followup_str:<20} {status:<15} {user_name:<15}")
        
        cur.close()
        conn.close()
        
        print(f"\n✅ Analysis completed successfully!")
        print(f"📅 Target date: {target_date_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"📊 Total overdue leads found: {total_overdue}")
        
    except Exception as e:
        print(f"❌ Error checking overdue leads: {e}")

if __name__ == "__main__":
    check_overdue_leads()
