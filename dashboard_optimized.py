"""
Dashboard optimization module containing performance-optimized functions for the CRM dashboard.
This file serves as a reference implementation and backup of the optimized dashboard code.
The optimizations have been integrated into application.py.
"""

from datetime import datetime, timedelta, time
from pytz import timezone
import pytz
from flask import jsonify
from sqlalchemy import func
from models import db, Lead, User, DailyFollowupCount, WorkedLead

# Initialize timezone
ist = timezone('Asia/Kolkata')

def get_initial_followup_count(user_id, date):
    """Get the initial followup count for a user on a specific date."""
    daily_count = DailyFollowupCount.query.filter_by(
        user_id=user_id, 
        date=date
    ).first()
    
    if daily_count:
        return daily_count.initial_count
    else:
        start_datetime = datetime.combine(date, time.min)
        end_datetime = datetime.combine(date + timedelta(days=1), time.min)
        
        current_count = Lead.query.filter(
            Lead.creator_id == user_id,
            Lead.followup_date >= start_datetime,
            Lead.followup_date < end_datetime
        ).count()
        
        # Create record
        daily_count = DailyFollowupCount(
            user_id=user_id,
            date=date,
            initial_count=current_count
        )
        try:
            db.session.add(daily_count)
            db.session.commit()
        except:
            db.session.rollback()
        
        return current_count

def capture_daily_snapshot():
    """Capture daily snapshot of followup counts at 5AM IST."""
    try:
        print(f"Running daily snapshot at {datetime.now(ist)}")
        
        # Get today's date in IST
        today = datetime.now(ist).date()
        today_start = ist.localize(datetime.combine(today, time.min))
        tomorrow_start = today_start + timedelta(days=1)
        
        # Convert to UTC for database queries
        today_start_utc = today_start.astimezone(pytz.UTC)
        tomorrow_start_utc = tomorrow_start.astimezone(pytz.UTC)
        
        # Get all users
        users = User.query.all()
        
        for user in users:
            # Count leads scheduled for today
            followup_count = Lead.query.filter(
                Lead.creator_id == user.id,
                Lead.followup_date >= today_start_utc,
                Lead.followup_date < tomorrow_start_utc
            ).count()
            
            # Create or update daily count record
            daily_count = DailyFollowupCount.query.filter_by(
                user_id=user.id,
                date=today
            ).first()
            
            if daily_count:
                daily_count.initial_count = followup_count
            else:
                daily_count = DailyFollowupCount(
                    user_id=user.id,
                    date=today,
                    initial_count=followup_count
                )
                db.session.add(daily_count)
            
            print(f"User {user.name}: {followup_count} followups fixed for {today}")
        
        db.session.commit()
        print(f"Daily snapshot completed successfully for {today}")
        
    except Exception as e:
        print(f"Error in daily snapshot: {e}")
        db.session.rollback()

def get_worked_leads_for_date(user_id, date):
    """Get count of worked leads for a specific user on a specific date."""
    try:
        worked_count = WorkedLead.query.filter_by(
            user_id=user_id,
            work_date=date
        ).count()
        return worked_count
    except Exception as e:
        print(f"Error getting worked leads count: {e}")
        return 0

def calculate_completion_rate(initial_count, worked_count):
    """Calculate completion rate as percentage."""
    if initial_count == 0:
        return 100.0
    return round((worked_count / initial_count) * 100, 1)

def get_user_performance(user, target_date):
    """Calculate performance metrics for a specific user."""
    # Get initial followup count
    initial_count = get_initial_followup_count(user.id, target_date)
    
    # Get worked leads count
    worked_count = get_worked_leads_for_date(user.id, target_date)
    
    # Calculate metrics
    completion_rate = calculate_completion_rate(initial_count, worked_count)
    pending_count = max(0, initial_count - worked_count)
    
    # Get user's total leads
    user_total = Lead.query.filter(
        Lead.creator_id == user.id
    ).count()
    
    # Get status counts
    status_counts = dict(
        Lead.query.with_entities(
            Lead.status,
            func.count(Lead.id)
        ).filter(
            Lead.creator_id == user.id
        ).group_by(Lead.status).all()
    )
    
    return {
        'user': user,
        'initial_followups': initial_count,
        'pending_followups': pending_count,
        'worked_followups': worked_count,
        'completion_rate': completion_rate,
        'leads_created': user_total,
        'confirmed': status_counts.get('Confirmed', 0),
        'completed': status_counts.get('Completed', 0)
    } 