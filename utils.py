"""
Utility functions for the CRM application.
Helper functions for data processing, formatting, and common operations.
"""
import re
from datetime import datetime, time
from pytz import timezone
import pytz

# Timezone
ist = timezone('Asia/Kolkata')

# Mobile mapping
USER_MOBILE_MAPPING = {
    'Hemlata': '9672562111',
    'Sneha': '+919672764111'
}


def normalize_mobile_number(mobile):
    """
    Normalize mobile number to accept three formats:
    1. +91XXXXXXXXXX (13 characters: +91 + 10 digits)
    2. XXXXXXXXXX (10 digits)
    3. 91XXXXXXXXXX (12 digits: 91 + 10 digits)

    Returns normalized mobile number (10 digits) or None if invalid.
    """
    if not mobile:
        return None

    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', str(mobile))

    # Handle +91 format
    if cleaned.startswith('+91'):
        digits = cleaned[3:]
        if len(digits) == 10:
            return digits
    # Handle 91XXXXXXXXXX format
    elif cleaned.startswith('91'):
        digits = cleaned[2:]
        if len(digits) == 10:
            return digits
    # Handle XXXXXXXXXX format (10 digits)
    elif len(cleaned) == 10:
        return cleaned

    return None


def utc_to_ist(utc_dt):
    """Convert UTC datetime to IST"""
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    ist_tz = pytz.timezone('Asia/Kolkata')
    return utc_dt.astimezone(ist_tz)


def to_ist_iso(dt):
    """Convert datetime to IST ISO string for API responses"""
    if dt is None:
        return None
    ist_dt = utc_to_ist(dt)
    return ist_dt.isoformat() if ist_dt else None

