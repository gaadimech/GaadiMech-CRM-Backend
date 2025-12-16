"""
Enterprise-grade Teleobi WhatsApp API Client
Implements world-class rate limiting, error handling, and quality checks
"""
import os
import requests
import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TemplateType(Enum):
    """WhatsApp template types"""
    UTILITY = "utility"
    MARKETING = "marketing"


class MessageStatus(Enum):
    """Message delivery status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


@dataclass
class Template:
    """WhatsApp template structure"""
    template_id: str  # WhatsApp template ID (long number)
    template_name: str
    template_type: TemplateType
    status: str  # Approved, Pending, Rejected
    variables: Dict
    category: str  # transactional, marketing
    language: str
    header_info: Dict = None  # Header information (image, video, etc.)
    template_json: str = None  # Full template JSON from Teleobi
    teleobi_template_id: str = None  # Teleobi internal template ID (for sending, e.g., 195735)
    whatsapp_business_id: Optional[int] = None  # WhatsApp Business ID (per template, for message status API)
    created_at: Optional[datetime] = None


@dataclass
class SendResult:
    """Result of a message send operation"""
    success: bool
    wa_message_id: Optional[str] = None
    error_message: Optional[str] = None
    status_code: Optional[int] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[datetime] = None


class TeleobiRateLimiter:
    """
    Enterprise-grade rate limiter following industry best practices
    Implements tier-based rate limiting similar to Twilio, MessageBird, etc.
    """

    # Conservative rate limits (messages per second)
    # These are more conservative than WhatsApp's limits to ensure safety
    TIER_LIMITS = {
        1: {"per_second": 0.5, "per_minute": 20, "per_hour": 1000, "per_day": 1000},
        2: {"per_second": 1.0, "per_minute": 50, "per_hour": 5000, "per_day": 10000},
        3: {"per_second": 2.0, "per_minute": 100, "per_hour": 50000, "per_day": 100000},
        4: {"per_second": 5.0, "per_minute": 300, "per_hour": 500000, "per_day": None}  # Unlimited
    }

    def __init__(self, tier: int = 1):
        self.tier = tier
        self.limits = self.TIER_LIMITS.get(tier, self.TIER_LIMITS[1])

        # Track sends in time windows
        self.secondly_sends = []  # List of timestamps
        self.minutely_sends = []  # List of timestamps
        self.hourly_sends = []  # List of timestamps
        self.daily_sends = []  # List of timestamps

        # Lock for thread safety
        self._lock = None
        try:
            import threading
            self._lock = threading.Lock()
        except ImportError:
            pass

    def _acquire_lock(self):
        """Acquire lock if available"""
        if self._lock:
            self._lock.acquire()

    def _release_lock(self):
        """Release lock if available"""
        if self._lock:
            self._lock.release()

    def _clean_old_entries(self):
        """Remove old entries outside time windows"""
        now = time.time()

        # Clean second window (last 1 second)
        self.secondly_sends = [t for t in self.secondly_sends if now - t < 1.0]

        # Clean minute window (last 60 seconds)
        self.minutely_sends = [t for t in self.minutely_sends if now - t < 60.0]

        # Clean hour window (last 3600 seconds)
        self.hourly_sends = [t for t in self.hourly_sends if now - t < 3600.0]

        # Clean day window (last 86400 seconds)
        self.daily_sends = [t for t in self.daily_sends if now - t < 86400.0]

    def can_send(self) -> Tuple[bool, Optional[float]]:
        """
        Check if we can send a message now
        Returns: (can_send, wait_time_seconds)
        """
        self._acquire_lock()
        try:
            self._clean_old_entries()
            now = time.time()

            # Check per-second limit
            if len(self.secondly_sends) >= self.limits["per_second"]:
                wait_time = 1.0 - (now - self.secondly_sends[0]) if self.secondly_sends else 1.0
                return False, max(0.1, wait_time)

            # Check per-minute limit
            if len(self.minutely_sends) >= self.limits["per_minute"]:
                wait_time = 60.0 - (now - self.minutely_sends[0]) if self.minutely_sends else 60.0
                return False, max(0.1, wait_time)

            # Check per-hour limit
            if len(self.hourly_sends) >= self.limits["per_hour"]:
                wait_time = 3600.0 - (now - self.hourly_sends[0]) if self.hourly_sends else 3600.0
                return False, max(0.1, wait_time)

            # Check per-day limit (if applicable)
            if self.limits["per_day"] and len(self.daily_sends) >= self.limits["per_day"]:
                wait_time = 86400.0 - (now - self.daily_sends[0]) if self.daily_sends else 86400.0
                return False, max(0.1, wait_time)

            return True, None

        finally:
            self._release_lock()

    def record_send(self):
        """Record that a message was sent"""
        self._acquire_lock()
        try:
            now = time.time()
            self.secondly_sends.append(now)
            self.minutely_sends.append(now)
            self.hourly_sends.append(now)
            self.daily_sends.append(now)
        finally:
            self._release_lock()

    def get_stats(self) -> Dict:
        """Get current rate limit statistics"""
        self._clean_old_entries()
        return {
            "tier": self.tier,
            "per_second": {
                "used": len(self.secondly_sends),
                "limit": self.limits["per_second"]
            },
            "per_minute": {
                "used": len(self.minutely_sends),
                "limit": self.limits["per_minute"]
            },
            "per_hour": {
                "used": len(self.hourly_sends),
                "limit": self.limits["per_hour"]
            },
            "per_day": {
                "used": len(self.daily_sends),
                "limit": self.limits["per_day"] or "unlimited"
            }
        }


class TeleobiClient:
    """
    Enterprise-grade Teleobi WhatsApp API client
    Implements comprehensive error handling, rate limiting, and quality checks
    """

    def __init__(self, api_url: str = None, auth_token: str = None, phone_number_id: str = None, tier: int = 1):
        self.api_url = api_url or os.getenv('TELEOBI_API_URL', 'https://dash.teleobi.com/api/v1')
        self.auth_token = auth_token or os.getenv('TELEOBI_AUTH_TOKEN')
        self.phone_number_id = phone_number_id or os.getenv('TELEOBI_PHONE_NUMBER_ID')
        self.tier = tier

        if not self.auth_token:
            raise ValueError("TELEOBI_AUTH_TOKEN is required")
        if not self.phone_number_id:
            raise ValueError("TELEOBI_PHONE_NUMBER_ID is required")

        # Initialize rate limiter
        self.rate_limiter = TeleobiRateLimiter(tier=tier)

        # Request session with timeout
        self.session = requests.Session()
        self.session.timeout = 30

        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds

        # Quality tracking
        self.quality_metrics = {
            "total_sends": 0,
            "successful_sends": 0,
            "failed_sends": 0,
            "rate_limit_hits": 0,
            "last_error": None
        }

    def _make_request(self, endpoint: str, method: str = "POST", data: Dict = None, params: Dict = None) -> requests.Response:
        """
        Make API request with error handling and retries
        """
        url = f"{self.api_url}/{endpoint}"

        # Add auth token to data/params
        if data is None:
            data = {}
        if params is None:
            params = {}

        if method.upper() == "POST":
            data['apiToken'] = self.auth_token
        else:
            params['apiToken'] = self.auth_token

        for attempt in range(self.max_retries):
            try:
                if method.upper() == "POST":
                    response = self.session.post(url, data=data, params=params, timeout=30)
                else:
                    response = self.session.get(url, params=params, timeout=30)

                # Check for rate limiting
                if response.status_code == 429:
                    self.quality_metrics["rate_limit_hits"] += 1
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limit hit. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue

                return response

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise

        raise Exception("Max retries exceeded")

    def get_templates(self, force_refresh: bool = False) -> List[Template]:
        """
        Fetch all WhatsApp templates from Teleobi
        Categorizes them as Utility or Marketing
        """
        try:
            response = self._make_request("whatsapp/template/list", data={
                'phone_number_id': self.phone_number_id
            })

            if response.status_code != 200:
                logger.error(f"Failed to fetch templates: {response.status_code} - {response.text}")
                return []

            data = response.json()
            if data.get('status') != '1':
                logger.error(f"API returned error: {data.get('message', 'Unknown error')}")
                return []

            templates_data = data.get('message', [])
            if not isinstance(templates_data, list):
                templates_data = [templates_data] if templates_data else []

            templates = []
            for template_data in templates_data:
                try:
                    # Parse variables from template_json and body_content
                    variables = {}
                    header_info = {
                        'has_image': False,
                        'has_video': False,
                        'has_document': False,
                        'header_type': None,
                        'header_subtype': None
                    }

                    template_json_str = template_data.get('template_json', '{}')

                    # CRITICAL: Check multiple sources for category
                    # 1. Top-level template_category field (most reliable)
                    # 2. template_json.category field
                    # 3. Fallback to check_wp_type

                    template_category_top = template_data.get('template_category', '').upper()  # Top-level field
                    category_from_json = ''
                    if template_json_str:
                        try:
                            template_json_parsed = json.loads(template_json_str) if isinstance(template_json_str, str) else template_json_str
                            category_from_json = template_json_parsed.get('category', '').upper()  # MARKETING or UTILITY
                        except:
                            pass

                    # Also check other top-level fields as fallback
                    category_top = template_data.get('category', '').lower()
                    check_wp_type = template_data.get('check_wp_type', '').lower()

                    # Determine template type - prioritize template_category (top-level) first
                    # This is the most accurate field from Teleobi API
                    if template_category_top:
                        if 'MARKETING' in template_category_top:
                            template_type = TemplateType.MARKETING
                        elif 'UTILITY' in template_category_top or 'TRANSACTIONAL' in template_category_top:
                            template_type = TemplateType.UTILITY
                        else:
                            # If template_category exists but unclear, check other sources
                            if category_from_json == 'MARKETING':
                                template_type = TemplateType.MARKETING
                            elif category_from_json == 'UTILITY' or category_from_json == 'TRANSACTIONAL':
                                template_type = TemplateType.UTILITY
                            else:
                                template_type = TemplateType.UTILITY
                    elif category_from_json:
                        # Fallback to template_json.category
                        if category_from_json == 'MARKETING':
                            template_type = TemplateType.MARKETING
                        elif category_from_json == 'UTILITY' or category_from_json == 'TRANSACTIONAL':
                            template_type = TemplateType.UTILITY
                        else:
                            template_type = TemplateType.UTILITY
                    else:
                        # Final fallback: check other fields
                        if 'marketing' in category_top or 'marketing' in check_wp_type:
                            template_type = TemplateType.MARKETING
                        elif 'transactional' in category_top or 'utility' in category_top or 'utility' in check_wp_type:
                            template_type = TemplateType.UTILITY
                        else:
                            # Default to UTILITY if unclear (safer for compliance)
                            template_type = TemplateType.UTILITY
                            logger.warning(f"Template {template_data.get('template_name')} has unclear category. Defaulting to UTILITY.")

                    # Debug logging for category detection (especially for marketing templates)
                    template_name = template_data.get('template_name', '')
                    if 'express_90mins' in template_name.lower() or '2906' in template_name.lower() or 'time_2906' in template_name.lower() or template_type == TemplateType.MARKETING:
                        logger.info(f"🔍 Template {template_name}: template_category={template_category_top}, template_json.category={category_from_json}, check_wp_type={check_wp_type}, final_type={template_type.value}")
                    body_content = template_data.get('body_content', '')
                    header_content = template_data.get('header_content', '')
                    header_type = template_data.get('header_type', '')
                    header_subtype = template_data.get('header_subtype', '')

                    # Check for header media types
                    if header_type and header_type.lower() == 'media':
                        if header_subtype:
                            header_info['has_image'] = header_subtype.lower() == 'image'
                            header_info['has_video'] = header_subtype.lower() == 'video'
                            header_info['has_document'] = header_subtype.lower() == 'document'
                        header_info['header_type'] = header_type
                        header_info['header_subtype'] = header_subtype

                    if template_json_str:
                        try:
                            # Parse template_json (already parsed above for category, but parse again for variables)
                            template_json = json.loads(template_json_str) if isinstance(template_json_str, str) else template_json_str

                            # Extract variables from template components
                            components = template_json.get('components', [])

                            # Extract body variables
                            for component in components:
                                if component.get('type') == 'body':
                                    body_text = component.get('text', '')
                                    # Find ONLY actual variable placeholders {{1}}, {{2}}, etc.
                                    # Must match the exact pattern {{number}} - not just any number
                                    import re
                                    # Match {{1}}, {{2}}, etc. - ensure it's the exact placeholder format
                                    var_matches = re.findall(r'\{\{(\d+)\}\}', body_text)
                                    # Remove duplicates and sort
                                    unique_vars = sorted(set(var_matches), key=lambda x: int(x))
                                    for var_num in unique_vars:
                                        # Only add if it's a valid variable (1-100 range to avoid matching years, etc.)
                                        if 1 <= int(var_num) <= 100:
                                            variables[f"body_var_{var_num}"] = {
                                                'type': 'text',
                                                'position': int(var_num),
                                                'label': f'Variable {var_num}',
                                                'required': True
                                            }

                                # Check header for variables
                                elif component.get('type') == 'header':
                                    format_type = component.get('format', '')
                                    if format_type == 'image' or format_type == 'video' or format_type == 'document':
                                        header_info['has_image'] = format_type == 'image'
                                        header_info['has_video'] = format_type == 'video'
                                        header_info['has_document'] = format_type == 'document'
                                        header_info['header_type'] = 'media'
                                        header_info['header_subtype'] = format_type

                                    # Check for header text variables
                                    example = component.get('example', {})
                                    if isinstance(example, dict):
                                        header_handle = example.get('header_handle', [])
                                        if header_handle and len(header_handle) > 0:
                                            # Header has media that needs to be provided
                                            pass

                            # Also check body_content directly for variables (fallback)
                            if body_content and not variables:
                                import re
                                # Match ONLY {{number}} placeholders
                                var_matches = re.findall(r'\{\{(\d+)\}\}', body_content)
                                # Remove duplicates and sort
                                unique_vars = sorted(set(var_matches), key=lambda x: int(x))
                                for var_num in unique_vars:
                                    # Only add if it's a valid variable (1-100 range)
                                    if 1 <= int(var_num) <= 100:
                                        if f"body_var_{var_num}" not in variables:
                                            variables[f"body_var_{var_num}"] = {
                                                'type': 'text',
                                                'position': int(var_num),
                                                'label': f'Variable {var_num}',
                                                'required': True
                                            }
                        except Exception as e:
                            logger.warning(f"Error parsing template JSON: {str(e)}")
                            # Fallback: simple extraction from body_content
                            if body_content and not variables:
                                import re
                                # Match ONLY {{number}} placeholders
                                var_matches = re.findall(r'\{\{(\d+)\}\}', body_content)
                                # Remove duplicates and sort
                                unique_vars = sorted(set(var_matches), key=lambda x: int(x))
                                for var_num in unique_vars:
                                    # Only add if it's a valid variable (1-100 range)
                                    if 1 <= int(var_num) <= 100:
                                        variables[f"body_var_{var_num}"] = {
                                            'type': 'text',
                                            'position': int(var_num),
                                            'label': f'Variable {var_num}',
                                            'required': True
                                        }

                    # Extract header info from variables (it was stored there temporarily)
                    header_info = variables.pop('_header_info', {}) if '_header_info' in variables else header_info

                    # Get Teleobi internal template ID (for sending) and WhatsApp template ID
                    teleobi_id = str(template_data.get('id', ''))  # Teleobi internal ID (e.g., 195735)
                    whatsapp_template_id = template_data.get('template_id', '')  # WhatsApp template ID
                    whatsapp_business_id = template_data.get('whatsapp_business_id')  # Store for message status API

                    # Store whatsapp_business_id in template_json for later use
                    if template_json_str and whatsapp_business_id:
                        try:
                            template_json_parsed = json.loads(template_json_str) if isinstance(template_json_str, str) else template_json_str
                            template_json_parsed['_whatsapp_business_id'] = whatsapp_business_id
                            template_json_str = json.dumps(template_json_parsed)
                        except:
                            pass

                    # Convert whatsapp_business_id to int if available
                    whatsapp_business_id_int = None
                    if whatsapp_business_id:
                        try:
                            whatsapp_business_id_int = int(whatsapp_business_id)
                        except (ValueError, TypeError):
                            pass

                    template = Template(
                        template_id=whatsapp_template_id,  # WhatsApp template ID
                        template_name=template_data.get('template_name', ''),
                        template_type=template_type,
                        status=template_data.get('status', 'Unknown'),
                        variables=variables,
                        category=(template_category_top or category_from_json or category_top or check_wp_type or 'general').lower() if (template_category_top or category_from_json or category_top or check_wp_type) else 'general',
                        language=template_data.get('locale', 'en_US'),
                        header_info=header_info,
                        template_json=template_json_str,  # Store full template JSON
                        teleobi_template_id=teleobi_id,  # Store Teleobi internal ID
                        whatsapp_business_id=whatsapp_business_id_int  # Store WhatsApp Business ID per template
                    )
                    templates.append(template)
                except Exception as e:
                    logger.error(f"Error parsing template: {str(e)}")
                    continue

            logger.info(f"Fetched {len(templates)} templates from Teleobi")
            return templates

        except Exception as e:
            logger.error(f"Error fetching templates: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def send_template_message(
        self,
        phone_number: str,
        template_name: str,
        variables: Dict = None,
        template_id: str = None,  # Template ID from Teleobi (numeric)
        validate_before_send: bool = True
    ) -> SendResult:
        """
        Send a WhatsApp template message with comprehensive validation

        Args:
            phone_number: Recipient phone number (with country code, no +)
            template_name: Name of the template to send
            variables: Template variables as dict
            validate_before_send: Whether to validate before sending

        Returns:
            SendResult with success status and message ID
        """
        # Pre-send validation
        if validate_before_send:
            validation_result = self._validate_before_send(phone_number, template_name)
            if not validation_result[0]:
                return SendResult(
                    success=False,
                    error_message=validation_result[1],
                    status_code=400
                )

        # Rate limiting check
        can_send, wait_time = self.rate_limiter.can_send()
        if not can_send:
            logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
            time.sleep(wait_time)
            # Re-check after waiting
            can_send, wait_time = self.rate_limiter.can_send()
            if not can_send:
                return SendResult(
                    success=False,
                    error_message=f"Rate limit exceeded. Please wait {wait_time:.2f} seconds.",
                    status_code=429
                )

        # Clean phone number
        phone_number = self._clean_phone_number(phone_number)

        # CRITICAL: Template messages use /whatsapp/send/template endpoint
        # Format: templateVariable-{template_name}-{variable_number}={value}
        # Example: templateVariable-one-1=one, templateVariable-two-2=two

        if not template_id:
            logger.error(f"Template ID is required for sending template messages. Template: {template_name}")
            return SendResult(
                success=False,
                error_message="Template ID is required. Please sync templates first.",
                status_code=400
            )

        # Prepare request data for TEMPLATE message
        # Based on Teleobi API: https://dash.teleobi.com/api/v1/whatsapp/send/template
        data = {
            'phone_number_id': self.phone_number_id,
            'phone_number': phone_number,
            'template_id': template_id  # Use template_id (numeric) not template_name
        }

        # Add variables in Teleobi's expected format
        # Based on example: templateVariable-one-1=one, templateVariable-two-2=two
        # Format appears to be: templateVariable-{identifier}-{number}
        # We'll use template name slug as identifier: templateVariable-{template_slug}-{var_num}

        if variables:
            # Convert template name to a clean slug format
            # Remove special chars, keep alphanumeric and hyphens
            import re
            template_slug = re.sub(r'[^a-z0-9-]', '', template_name.lower().replace('_', '-').replace(' ', '-'))

            # Process variables and convert to Teleobi format
            for key, value in variables.items():
                if key.startswith('_') or not value:
                    continue  # Skip internal keys and empty values

                # Extract variable number from body_var_1, body_var_2, etc.
                if key.startswith('body_var_'):
                    var_num = key.replace('body_var_', '')
                    # Format: templateVariable-{template_slug}-{var_num}
                    # Example: templateVariable-de-the-best-0307-1
                    template_var_key = f'templateVariable-{template_slug}-{var_num}'
                    data[template_var_key] = value
                    logger.debug(f"Variable mapping: {key} -> {template_var_key} = {value}")
                elif key == 'header_image_url':
                    # Header image - CORRECT parameter name: template_header_media_url
                    # Based on Teleobi API console example:
                    # template_header_media_url=https://bot-data.s3.ap-southeast-1.wasabisys.com/...
                    if value:  # Only add if value is provided
                        # Validate URL format
                        if not value.startswith('http://') and not value.startswith('https://'):
                            logger.warning(f"Header image URL doesn't start with http/https: {value}")
                            continue  # Skip invalid URLs

                        # Use the correct parameter name from Teleobi API console
                        data['template_header_media_url'] = value
                        logger.info(f"Adding header image as 'template_header_media_url': {value}")
                else:
                    # For other formats, try to extract number
                    if key.startswith('var_'):
                        var_num = key.replace('var_', '')
                        template_var_key = f'templateVariable-{template_slug}-{var_num}'
                        data[template_var_key] = value
                        logger.debug(f"Variable mapping: {key} -> {template_var_key} = {value}")
                    else:
                        # Unknown format, log warning but try to use it
                        logger.warning(f"Unknown variable format: {key}, using as-is")
                        data[key] = value

        try:
            # CRITICAL: Use the correct template endpoint
            # Endpoint: /whatsapp/send/template (not /whatsapp/send)
            # This is for messages outside 24-hour window
            template_endpoint = "whatsapp/send/template"

            # Log what we're sending for debugging
            logger.info(f"📤 Sending template message to {phone_number}")
            logger.info(f"Template ID: {template_id}, Template Name: {template_name}")
            logger.debug(f"Request data: {data}")

            response = self._make_request(template_endpoint, data=data)

            # Record send attempt
            self.quality_metrics["total_sends"] += 1

            if response.status_code == 200:
                response_data = response.json()

                if response_data.get('status') == '1':
                    # Success
                    self.rate_limiter.record_send()
                    self.quality_metrics["successful_sends"] += 1

                    wa_message_id = response_data.get('wa_message_id')
                    logger.info(f"✅ Message sent successfully to {phone_number}. WA Message ID: {wa_message_id}")

                    return SendResult(
                        success=True,
                        wa_message_id=wa_message_id,
                        status_code=200
                    )
                else:
                    # API returned error - status is not '1'
                    error_msg = response_data.get('message', 'Unknown error')
                    logger.error(f"❌ Teleobi API error for {phone_number}: {error_msg}")
                    logger.error(f"Full response: {response_data}")
                    logger.error(f"Request data sent: {data}")
                    self.quality_metrics["failed_sends"] += 1
                    self.quality_metrics["last_error"] = error_msg

                    return SendResult(
                        success=False,
                        error_message=error_msg,
                        status_code=200  # API returned 200 but with error status
                    )
            else:
                # HTTP error
                self.quality_metrics["failed_sends"] += 1
                error_text = response.text[:500]  # Get more error details
                error_msg = f"HTTP {response.status_code}: {error_text}"
                logger.error(f"HTTP error sending message: {error_msg}")
                try:
                    error_data = response.json()
                    if error_data.get('message'):
                        error_msg = error_data.get('message')
                    logger.error(f"Error details: {error_data}")
                except:
                    pass
                self.quality_metrics["last_error"] = error_msg

                return SendResult(
                    success=False,
                    error_message=error_msg,
                    status_code=response.status_code
                )

        except Exception as e:
            self.quality_metrics["failed_sends"] += 1
            error_msg = f"Exception: {str(e)}"
            self.quality_metrics["last_error"] = error_msg
            logger.error(f"Error sending message: {error_msg}")

            return SendResult(
                success=False,
                error_message=error_msg,
                status_code=500
            )

    def _validate_before_send(self, phone_number: str, template_name: str) -> Tuple[bool, str]:
        """
        Comprehensive pre-send validation
        Returns: (is_valid, error_message)
        """
        # Validate phone number format
        if not phone_number:
            return False, "Phone number is required"

        # Clean and validate phone number
        cleaned = self._clean_phone_number(phone_number)
        if len(cleaned) < 10 or len(cleaned) > 15:
            return False, f"Invalid phone number format: {phone_number}"

        # Check if phone number contains only digits
        if not cleaned.isdigit():
            return False, f"Phone number must contain only digits: {phone_number}"

        # Validate template name
        if not template_name:
            return False, "Template name is required"

        # Check rate limits
        can_send, wait_time = self.rate_limiter.can_send()
        if not can_send:
            return False, f"Rate limit reached. Please wait {wait_time:.2f} seconds."

        # Check quality metrics (prevent sending if failure rate is too high)
        if self.quality_metrics["total_sends"] > 0:
            failure_rate = self.quality_metrics["failed_sends"] / self.quality_metrics["total_sends"]
            if failure_rate > 0.5:  # More than 50% failure rate
                return False, "High failure rate detected. Please check account status."

        return True, ""

    def _clean_phone_number(self, phone_number: str) -> str:
        """Clean phone number to standard format"""
        # Remove all non-digit characters
        cleaned = ''.join(filter(str.isdigit, phone_number))

        # Remove leading + if present (already handled by filter)
        # Ensure country code is present (add 91 for India if 10 digits)
        if len(cleaned) == 10:
            cleaned = '91' + cleaned

        return cleaned

    def get_message_status(self, wa_message_id: str, whatsapp_bot_id: int = None) -> Dict:
        """Get delivery status of a message

        Args:
            wa_message_id: WhatsApp message ID (e.g., wamid.HBgM...)
            whatsapp_bot_id: WhatsApp bot ID (required by Teleobi API)
        """
        try:
            data = {
                'wa_message_id': wa_message_id
            }

            # whatsapp_bot_id is REQUIRED by Teleobi API according to documentation
            # Try to get it from parameter, environment variable, or template cache
            if whatsapp_bot_id:
                data['whatsapp_bot_id'] = whatsapp_bot_id
            else:
                # Try to get from environment variable
                env_bot_id = os.getenv('TELEOBI_WHATSAPP_BOT_ID')
                if env_bot_id:
                    try:
                        data['whatsapp_bot_id'] = int(env_bot_id)
                    except (ValueError, TypeError):
                        logger.warning(f"TELEOBI_WHATSAPP_BOT_ID is not a valid integer: {env_bot_id}")
                else:
                    logger.warning("whatsapp_bot_id not provided and TELEOBI_WHATSAPP_BOT_ID not set. API call may fail.")

            logger.info(f"Fetching message status for WA Message ID: {wa_message_id}, whatsapp_bot_id: {data.get('whatsapp_bot_id', 'not provided')}")
            response = self._make_request("whatsapp/get/message-status", data=data)

            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"Status API response: {response_data}")

                if response_data.get('status') == '1':
                    message_data = response_data.get('message', {})
                    logger.info(f"Message status data: {message_data}")
                    return message_data
                else:
                    logger.warning(f"Status API returned status != 1: {response_data.get('message', 'Unknown error')}")
            else:
                logger.warning(f"Status API returned status code {response.status_code}: {response.text}")

            return {}
        except Exception as e:
            logger.error(f"Error getting message status: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {}

    def get_quality_metrics(self) -> Dict:
        """Get current quality metrics"""
        success_rate = 0.0
        if self.quality_metrics["total_sends"] > 0:
            success_rate = self.quality_metrics["successful_sends"] / self.quality_metrics["total_sends"]

        return {
            **self.quality_metrics,
            "success_rate": success_rate,
            "rate_limit_stats": self.rate_limiter.get_stats()
        }

