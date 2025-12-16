#!/usr/bin/env python3
"""
Test script to verify Teleobi API connection and credentials
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

TELEOBI_API_URL = os.getenv('TELEOBI_API_URL', 'https://dash.teleobi.com/api/v1')
TELEOBI_AUTH_TOKEN = os.getenv('TELEOBI_AUTH_TOKEN')
TELEOBI_PHONE_NUMBER_ID = os.getenv('TELEOBI_PHONE_NUMBER_ID')

def test_api_connection():
    """Test Teleobi API connection by fetching templates"""
    print("=" * 60)
    print("Testing Teleobi API Connection")
    print("=" * 60)
    print(f"API URL: {TELEOBI_API_URL}")
    print(f"Phone Number ID: {TELEOBI_PHONE_NUMBER_ID}")
    print(f"Auth Token: {TELEOBI_AUTH_TOKEN[:20]}..." if TELEOBI_AUTH_TOKEN else "Auth Token: NOT SET")
    print()

    if not TELEOBI_AUTH_TOKEN:
        print("❌ ERROR: TELEOBI_AUTH_TOKEN not found in environment")
        return False

    if not TELEOBI_PHONE_NUMBER_ID:
        print("❌ ERROR: TELEOBI_PHONE_NUMBER_ID not found in environment")
        return False

    # Test 1: Fetch templates
    print("Test 1: Fetching templates...")
    try:
        url = f"{TELEOBI_API_URL}/whatsapp/template/list"
        params = {
            'apiToken': TELEOBI_AUTH_TOKEN,
            'phone_number_id': TELEOBI_PHONE_NUMBER_ID
        }

        response = requests.post(url, data=params, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS: API connection working!")
            print(f"Response Status: {data.get('status')}")

            if 'message' in data:
                template_data = data.get('message', {})
                if isinstance(template_data, dict):
                    print(f"Template ID: {template_data.get('id')}")
                    print(f"Template Name: {template_data.get('template_name')}")
                    print(f"Template Type: {template_data.get('template_type')}")
                    print(f"Status: {template_data.get('status')}")
                else:
                    print(f"Templates returned: {len(template_data) if isinstance(template_data, list) else 'N/A'}")

            return True
        else:
            print(f"❌ ERROR: API returned status {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Request failed - {str(e)}")
        return False
    except Exception as e:
        print(f"❌ ERROR: Unexpected error - {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_api_connection()
    sys.exit(0 if success else 1)

