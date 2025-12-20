"""
Firebase Cloud Messaging (FCM) notification service
Handles sending push notifications via Firebase Admin SDK
"""
import os
import json
import firebase_admin
from firebase_admin import credentials, messaging
from datetime import datetime
from pytz import timezone

ist = timezone('Asia/Kolkata')

# Initialize Firebase Admin SDK (singleton pattern)
_firebase_app = None

def initialize_firebase():
    """Initialize Firebase Admin SDK with service account credentials"""
    global _firebase_app
    
    if _firebase_app is not None:
        return _firebase_app
    
    try:
        # Option 1: Service account JSON file path
        service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
        
        # Option 2: Service account JSON as string
        service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
        
        # Option 3: Individual credentials from environment
        project_id = os.getenv('FIREBASE_PROJECT_ID')
        private_key = os.getenv('FIREBASE_PRIVATE_KEY')
        client_email = os.getenv('FIREBASE_CLIENT_EMAIL')
        
        cred = None
        
        if service_account_path and os.path.exists(service_account_path):
            # Load from file
            cred = credentials.Certificate(service_account_path)
            print("✅ Firebase initialized from service account file")
        elif service_account_json:
            # Load from JSON string
            try:
                print(f"   Attempting to parse FIREBASE_SERVICE_ACCOUNT_JSON...")
                print(f"   JSON length: {len(service_account_json)} characters")
                print(f"   JSON preview (first 100 chars): {service_account_json[:100]}...")
                
                service_account_dict = json.loads(service_account_json)
                print("   ✅ JSON parsed successfully")
                
                # Validate that required fields are present
                if 'private_key' not in service_account_dict:
                    raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON missing 'private_key' field")
                if 'project_id' not in service_account_dict:
                    raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON missing 'project_id' field")
                if 'client_email' not in service_account_dict:
                    raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON missing 'client_email' field")
                
                # Check private key format
                private_key = service_account_dict.get('private_key', '')
                if not private_key or not isinstance(private_key, str):
                    raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON has invalid private_key")
                
                print(f"   Private key length after JSON parse: {len(private_key)} characters")
                has_actual_newlines = chr(10) in private_key
                escaped_newline_str = '\\n'
                has_escaped_newlines = escaped_newline_str in private_key
                print(f"   Private key has actual newlines: {has_actual_newlines}")
                print(f"   Private key has escaped newlines: {has_escaped_newlines}")
                print(f"   Private key starts with BEGIN: {private_key.startswith('-----BEGIN')}")
                print(f"   Private key ends with END: {private_key.endswith('-----END PRIVATE KEY-----')}")
                
                # Fix private key newlines if needed
                # json.loads() should convert \n to actual newlines, but AWS might double-escape
                if escaped_newline_str in private_key:
                    # Check if we have literal \n (double-escaped) vs actual newlines
                    actual_newline = '\n'
                    if actual_newline not in private_key:
                        # Only escaped newlines, no actual newlines - need to convert
                        service_account_dict['private_key'] = private_key.replace(escaped_newline_str, actual_newline)
                        print("   ✅ Fixed escaped newlines in private_key (converted \\n to actual newlines)")
                    else:
                        # Has both - remove escaped ones
                        service_account_dict['private_key'] = private_key.replace(escaped_newline_str, '')
                        print("   ✅ Removed double-escaped newlines from private_key")
                
                # Final validation
                final_key = service_account_dict['private_key']
                if not final_key.startswith('-----BEGIN PRIVATE KEY-----'):
                    raise ValueError("Private key missing BEGIN marker after processing")
                if not final_key.endswith('-----END PRIVATE KEY-----\n') and not final_key.endswith('-----END PRIVATE KEY-----'):
                    raise ValueError("Private key missing END marker after processing")
                
                print(f"   Final private key length: {len(final_key)} characters")
                print(f"   Final private key newline count: {final_key.count(chr(10))}")
                
                cred = credentials.Certificate(service_account_dict)
                print("✅ Firebase initialized from JSON string")
                print(f"   Project ID: {service_account_dict.get('project_id', 'N/A')}")
                print(f"   Client Email: {service_account_dict.get('client_email', 'N/A')}")
            except json.JSONDecodeError as e:
                print(f"❌ Error decoding FIREBASE_SERVICE_ACCOUNT_JSON: {e}")
                print(f"   JSON string (first 500 chars): {service_account_json[:500]}...")
                print(f"   JSON string (last 200 chars): ...{service_account_json[-200:]}")
                raise
        elif project_id and private_key and client_email:
            # Load from individual environment variables
            # Fix private key format - handle both escaped and literal newlines
            private_key_clean = private_key.strip('"\'')  # Remove surrounding quotes
            
            # Handle various newline formats that AWS might use
            # Case 1: Literal \n strings (most common in AWS)
            if '\\n' in private_key_clean:
                private_key_clean = private_key_clean.replace('\\n', '\n')
            # Case 2: Raw string \n
            elif r'\n' in private_key_clean:
                private_key_clean = private_key_clean.replace(r'\n', '\n')
            # Case 3: Already has newlines but might have extra escaping
            elif '\n' in private_key_clean and '\\n' in private_key_clean:
                # Remove any remaining escaped newlines
                private_key_clean = private_key_clean.replace('\\n', '\n')
            
            # Ensure the key starts and ends with proper markers
            if not private_key_clean.startswith('-----BEGIN'):
                # Try to find where the key actually starts
                begin_idx = private_key_clean.find('-----BEGIN')
                if begin_idx > 0:
                    private_key_clean = private_key_clean[begin_idx:]
            
            # Validate key format
            if '-----BEGIN PRIVATE KEY-----' not in private_key_clean:
                raise ValueError("Private key missing BEGIN marker")
            if '-----END PRIVATE KEY-----' not in private_key_clean:
                raise ValueError("Private key missing END marker")
            
            # Debug: Log key info (first/last 50 chars only for security)
            key_length = len(private_key_clean)
            key_preview = private_key_clean[:50] + "..." + private_key_clean[-50:] if key_length > 100 else private_key_clean
            print(f"   Private Key Length: {key_length} characters")
            print(f"   Private Key Preview: {key_preview}")
            print(f"   Has BEGIN marker: {'-----BEGIN PRIVATE KEY-----' in private_key_clean}")
            print(f"   Has END marker: {'-----END PRIVATE KEY-----' in private_key_clean}")
            print(f"   Newline count: {private_key_clean.count(chr(10))}")
            
            service_account_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID', ''),
                "private_key": private_key_clean,
                "client_email": client_email,
                "client_id": os.getenv('FIREBASE_CLIENT_ID', ''),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL', ''),
            }
            cred = credentials.Certificate(service_account_dict)
            print(f"✅ Firebase initialized from environment variables (Project: {project_id})")
        else:
            # Try to load from default location (for local development)
            try:
                cred = credentials.Certificate("gaadimech-crm-firebase-adminsdk-fbsvc-d239efed44.json")
                print("✅ Firebase initialized from default file location")
            except Exception as e:
                print(f"❌ Firebase initialization failed: {e}")
                print("   Please set FIREBASE_SERVICE_ACCOUNT_PATH, FIREBASE_SERVICE_ACCOUNT_JSON, or individual credentials")
                return None
        
        _firebase_app = firebase_admin.initialize_app(cred)
        return _firebase_app
        
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        print(f"   Project ID: {os.getenv('FIREBASE_PROJECT_ID', 'NOT SET')}")
        print(f"   Client Email: {os.getenv('FIREBASE_CLIENT_EMAIL', 'NOT SET')}")
        print(f"   Private Key Present: {'YES' if os.getenv('FIREBASE_PRIVATE_KEY') else 'NO'}")
        import traceback
        traceback.print_exc()
        return None

def send_fcm_notification(fcm_token, title, body, data=None, url=None):
    """
    Send a push notification via FCM to a single device
    
    Args:
        fcm_token: FCM registration token
        title: Notification title
        body: Notification body
        data: Additional data payload (dict)
        url: URL to open when notification is clicked
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize Firebase if not already done
        if _firebase_app is None:
            initialize_firebase()
        
        if _firebase_app is None:
            print("❌ Firebase not initialized, cannot send notification")
            return False
        
        # Prepare notification payload
        notification = messaging.Notification(
            title=title,
            body=body,
        )
        
        # Prepare data payload
        data_payload = data or {}
        if url:
            data_payload['url'] = url
        
        # Create message
        message = messaging.Message(
            notification=notification,
            data={k: str(v) for k, v in data_payload.items()},  # FCM data must be strings
            token=fcm_token,
        )
        
        # Send message
        response = messaging.send(message)
        print(f"✅ Successfully sent FCM notification: {response}")
        return True
        
    except messaging.UnregisteredError:
        print(f"❌ FCM token is invalid or unregistered: {fcm_token[:20]}...")
        return False
    except messaging.InvalidArgumentError as e:
        print(f"❌ Invalid FCM token or message: {e}")
        return False
    except firebase_admin.exceptions.NotFoundError as e:
        print(f"❌ Firebase project not found or FCM not enabled: {e}")
        print("   Please verify:")
        print("   1. Firebase project ID is correct")
        print("   2. FCM API is enabled in Firebase Console")
        print("   3. Service account has proper permissions")
        return False
    except Exception as e:
        print(f"❌ Error sending FCM notification: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_fcm_notification_multicast(fcm_tokens, title, body, data=None, url=None):
    """
    Send push notifications via FCM to multiple devices
    
    Args:
        fcm_tokens: List of FCM registration tokens
        title: Notification title
        body: Notification body
        data: Additional data payload (dict)
        url: URL to open when notification is clicked
    
    Returns:
        dict: Results with success_count and failure_count
    """
    if not fcm_tokens:
        return {'success_count': 0, 'failure_count': 0, 'responses': []}
    
    try:
        # Initialize Firebase if not already done
        if _firebase_app is None:
            initialize_firebase()
        
        if _firebase_app is None:
            print("❌ Firebase not initialized, cannot send notifications")
            return {'success_count': 0, 'failure_count': len(fcm_tokens), 'responses': []}
        
        # Prepare notification payload
        notification = messaging.Notification(
            title=title,
            body=body,
        )
        
        # Prepare data payload
        data_payload = data or {}
        if url:
            data_payload['url'] = url
        
        # Create multicast message
        message = messaging.MulticastMessage(
            notification=notification,
            data={k: str(v) for k, v in data_payload.items()},  # FCM data must be strings
            tokens=fcm_tokens,
        )
        
        # Send message
        response = messaging.send_multicast(message)
        
        result = {
            'success_count': response.success_count,
            'failure_count': response.failure_count,
            'responses': []
        }
        
        # Process individual responses
        for idx, resp in enumerate(response.responses):
            if resp.success:
                result['responses'].append({
                    'token': fcm_tokens[idx],
                    'success': True,
                    'message_id': resp.message_id
                })
            else:
                result['responses'].append({
                    'token': fcm_tokens[idx],
                    'success': False,
                    'error': str(resp.exception) if resp.exception else 'Unknown error'
                })
        
        print(f"✅ FCM multicast: {result['success_count']} successful, {result['failure_count']} failed")
        return result
        
    except Exception as e:
        print(f"❌ Error sending FCM multicast notification: {e}")
        import traceback
        traceback.print_exc()
        return {'success_count': 0, 'failure_count': len(fcm_tokens), 'responses': []}

