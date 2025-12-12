#!/usr/bin/env python3
"""
Intelligent Text Parser for Customer Information Extraction
Extracts customer details from various message formats for GaadiMech CRM
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import pytz

# IST timezone
ist = pytz.timezone('Asia/Kolkata')

class CustomerInfoParser:
    """Intelligent parser for extracting customer information from text messages"""
    
    def __init__(self):
        # Car manufacturers and models mapping
        self.car_manufacturers = {
            'maruti': ['alto', 'swift', 'baleno', 'ciaz', 'dzire', 'wagon r', 'vitara brezza', 
                      'ertiga', 'xl6', 'ignis', 'celerio', 'eeco', 'omni', 'maruti 800', '800'],
            'hyundai': ['i10', 'i20', 'verna', 'creta', 'venue', 'santro', 'grand i10', 'tucson', 
                       'elantra', 'xcent', 'aura'],
            'honda': ['city', 'amaze', 'jazz', 'wr-v', 'civic', 'cr-v', 'accord', 'brio'],
            'toyota': ['innova', 'fortuner', 'etios', 'corolla', 'camry', 'glanza', 'urban cruiser', 
                      'yaris', 'prius'],
            'tata': ['nano', 'indica', 'indigo', 'vista', 'manza', 'bolt', 'zest', 'tigor', 'tiago', 
                    'nexon', 'hexa', 'safari', 'harrier', 'altroz'],
            'mahindra': ['scorpio', 'xuv500', 'xuv300', 'bolero', 'thar', 'marazzo', 'kuv100', 
                        'xylo', 'verito', 'logan'],
            'ford': ['figo', 'aspire', 'freestyle', 'ecosport', 'endeavour', 'fiesta', 'ikon'],
            'volkswagen': ['polo', 'vento', 'ameo', 'jetta', 'passat', 'tiguan'],
            'skoda': ['fabia', 'rapid', 'octavia', 'superb', 'kodiaq', 'karoq'],
            'nissan': ['micra', 'sunny', 'terrano', 'kicks', 'gt-r'],
            'renault': ['kwid', 'duster', 'captur', 'lodgy', 'scala', 'pulse', 'fluence']
        }
        
        # Service types mapping
        self.service_types = {
            'express service': 'Express Car Service',
            'express car service': 'Express Car Service',
            'car service': 'Express Car Service',
            'service': 'Express Car Service',
            'denting painting': 'Dent Paint',
            'dent paint': 'Dent Paint',
            'painting': 'Dent Paint',
            'denting': 'Dent Paint',
            'ac service': 'AC Service',
            'ac repair': 'AC Service',
            'air conditioning': 'AC Service',
            'car wash': 'Car Wash',
            'washing': 'Car Wash',
            'wash': 'Car Wash',
            'repairs': 'Repairs',
            'repair': 'Repairs',
            'general': 'Express Car Service',
            'general interest': 'Express Car Service'
        }
        
        # Pickup types mapping
        self.pickup_types = {
            'pickup': 'Pickup',
            'pnd': 'Pickup',
            'pick and drop': 'Pickup',
            'pick up': 'Pickup',
            'self walkin': 'Self Walkin',
            'self walk-in': 'Self Walkin',
            'walkin': 'Self Walkin',
            'walk-in': 'Self Walkin',
            'walk in': 'Self Walkin',
            'self': 'Self Walkin'
        }
        
        # Source types mapping
        self.sources = {
            'whatsapp': 'WhatsApp',
            'chatbot': 'Chatbot',
            'website': 'Website',
            'social media': 'Social Media',
            'facebook': 'Social Media',
            'instagram': 'Social Media',
            'twitter': 'Social Media'
        }
        
        # Common cities in India
        self.cities = ['delhi', 'mumbai', 'bangalore', 'chennai', 'kolkata', 'hyderabad', 'pune', 
                      'ahmedabad', 'jaipur', 'lucknow', 'kanpur', 'nagpur', 'indore', 'bhopal', 
                      'vadodara', 'coimbatore', 'ludhiana', 'kochi', 'visakhapatnam', 'agra',
                      'nashik', 'faridabad', 'prayagraj', 'rajkot', 'kalyan', 'vasai', 'varanasi',
                      'srinagar', 'aurangabad', 'dhanbad', 'amritsar', 'aligarh', 'gwalior',
                      'jalandhar', 'bhubaneswar', 'salem', 'warangal', 'guntur', 'bhilai',
                      'moradabad', 'ghaziabad', 'durg', 'jamshedpur', 'noida', 'gurugram', 'gurgaon']
    
    def parse_text(self, text: str) -> Dict[str, Optional[str]]:
        """Main method to parse text and extract customer information"""
        if not text or not text.strip():
            return self._get_empty_result()
        
        text = text.strip()
        result = self._get_empty_result()
        result['remarks'] = text  # Always store original text in remarks
        
        # Extract phone numbers
        result['mobile'] = self._extract_mobile_number(text)
        
        # Extract customer name
        result['customer_name'] = self._extract_customer_name(text)
        
        # Extract car information
        car_info = self._extract_car_info(text)
        result['car_manufacturer'] = car_info.get('manufacturer')
        result['car_model'] = car_info.get('model')
        
        # Extract service type
        result['service_type'] = self._extract_service_type(text)
        
        # Extract pickup type
        result['pickup_type'] = self._extract_pickup_type(text)
        
        # Extract scheduled date
        result['scheduled_date'] = self._extract_scheduled_date(text)
        
        # Extract source
        result['source'] = self._extract_source(text)
        
        # Extract status
        result['status'] = self._extract_status(text)
        
        return result
    
    def _get_empty_result(self) -> Dict[str, Optional[str]]:
        """Returns empty result dictionary with all fields set to None"""
        return {
            'mobile': None,
            'customer_name': None,
            'car_manufacturer': None,
            'car_model': None,
            'pickup_type': None,
            'service_type': None,
            'scheduled_date': None,
            'source': None,
            'status': None,
            'remarks': None
        }
    
    def _extract_mobile_number(self, text: str) -> Optional[str]:
        """Extract mobile number from text"""
        # Common patterns for mobile numbers (including emoji patterns)
        patterns = [
            r'📱\s*Mobile\s*[:\-]?\s*\+?91\s*[-\s]*(\d{5})\s*[-\s]*(\d{5})',  # 📱 Mobile: +91 XXXXX XXXXX
            r'📱\s*Mobile\s*[:\-]?\s*\+?91\s*[-\s]*(\d{10})',                  # 📱 Mobile: +91 XXXXXXXXXX
            r'📱\s*Mobile\s*[:\-]?\s*(\d{5})\s*[-\s]*(\d{5})',                # 📱 Mobile: XXXXX XXXXX
            r'📱\s*Mobile\s*[:\-]?\s*(\d{10})',                               # 📱 Mobile: XXXXXXXXXX
            r'\+91\s*[-\s]*(\d{5})\s*[-\s]*(\d{5})',                          # +91 XXXXX XXXXX
            r'\+91\s*[-\s]*(\d{10})',                                         # +91 XXXXXXXXXX
            r'91\s*[-\s]*(\d{10})',                                           # 91 XXXXXXXXXX
            r'(\d{5})\s*[-\s]*(\d{5})',                                       # XXXXX XXXXX
            r'(\d{10})',                                                       # XXXXXXXXXX
            r'\(\+91\s*(\d{10})\)',                                            # (+91 XXXXXXXXXX)
            r'\+91\s*(\d{5})\s*(\d{5})',                                       # +91 XXXXX XXXXX
            r'91\s*(\d{5})\s*(\d{5})',                                         # 91 XXXXX XXXXX
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                if isinstance(matches[0], tuple):
                    # Handle tuple matches (grouped patterns)
                    mobile = ''.join(matches[0])
                else:
                    mobile = matches[0]
                
                # Clean the mobile number
                mobile = re.sub(r'[^\d]', '', mobile)
                
                # Validate mobile number
                if len(mobile) == 10 and mobile.startswith(('6', '7', '8', '9')):
                    return '+91' + mobile
                elif len(mobile) == 12 and mobile.startswith('91'):
                    return '+' + mobile
                elif len(mobile) == 13 and mobile.startswith('+91'):
                    return mobile
        
        return None
    
    def _extract_customer_name(self, text: str) -> Optional[str]:
        """Extract customer name from text"""
        # Look for patterns like "Name: John Doe" or "John Doe (+91..." or emoji patterns
        patterns = [
            r'👤\s*Name\s*[:\-]?\s*([A-Za-z\s]+?)(?:\n|📱|$)',  # 👤 Name: John Doe
            r'Name\s*[:\-]?\s*([A-Za-z\s]+?)(?:\n|📱|$)',       # Name: John Doe
            r'([A-Za-z\s]+)\s*\(\+91',                          # Name (+91...)
            r'([A-Za-z\s]+)\s*\(\+?91',                         # Name (+91... or 91...)
            r'Customer\s*[:\-]?\s*([A-Za-z\s]+)',              # Customer: Name
            r'^([A-Za-z\s]+)\s*\(\+',                           # Name at start (+...)
            r'^([A-Za-z\s]+)\s*\d',                            # Name at start followed by number
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                name = matches[0].strip()
                # Filter out common non-name words
                if (len(name) > 2 and 
                    not any(word.lower() in name.lower() for word in ['car', 'service', 'manufacturer', 'model', 'city', 'fuel', 'type', 'date', 'time', 'slot', 'workshop', 'chosen', 'saturday', 'sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'enquiry', 'new', 'lead', 'mncapture', 'express', 'booking', 'completed']) and
                    not name.isdigit()):
                    return name.title()
        
        return None
    
    def _extract_car_info(self, text: str) -> Dict[str, Optional[str]]:
        """Extract car manufacturer and model from text"""
        text_lower = text.lower()
        result = {'manufacturer': None, 'model': None}
        
        # Look for "Car:" pattern (may contain both manufacturer and model)
        car_pattern = r'🚗\s*Car\s*[:\-]?\s*([a-zA-Z0-9\s]+?)(?:\n|🔧|$)'
        car_matches = re.findall(car_pattern, text, re.IGNORECASE)
        if car_matches:
            car_text = car_matches[0].strip()
            # Try to split manufacturer and model
            car_words = car_text.split()
            if len(car_words) >= 2:
                # First word might be manufacturer, rest is model
                potential_mfg = car_words[0].lower()
                for mfg in self.car_manufacturers.keys():
                    if mfg in potential_mfg or potential_mfg in mfg:
                        result['manufacturer'] = mfg.title()
                        result['model'] = ' '.join(car_words[1:]).title()
                        break
                if not result['manufacturer']:
                    # Try to find manufacturer in the text
                    for mfg in self.car_manufacturers.keys():
                        if mfg in car_text.lower():
                            result['manufacturer'] = mfg.title()
                            # Extract model (remove manufacturer name)
                            model_text = car_text.lower().replace(mfg, '').strip()
                            if model_text:
                                result['model'] = model_text.title()
                            break
                    if not result['manufacturer']:
                        # Just set as model if no manufacturer found
                        result['model'] = car_text.title()
        
        # Look for manufacturer patterns
        manufacturer_patterns = [
            r'car\s*manufacturer\s*[:\-]?\s*([a-zA-Z\s]+?)(?:\n|$)',
            r'manufacturer\s*[:\-]?\s*([a-zA-Z\s]+?)(?:\n|$)',
            r'make\s*[:\-]?\s*([a-zA-Z\s]+?)(?:\n|$)',
        ]
        
        if not result['manufacturer']:
            for pattern in manufacturer_patterns:
                matches = re.findall(pattern, text_lower)
                if matches:
                    manufacturer = matches[0].strip()
                    for mfg in self.car_manufacturers.keys():
                        if mfg in manufacturer.lower():
                            result['manufacturer'] = mfg.title()
                            break
                    if result['manufacturer']:
                        break
        
        # Look for model patterns (including emoji pattern)
        model_patterns = [
            r'🚗\s*Car\s*Model\s*[:\-]?\s*([a-zA-Z0-9\s]+?)(?:\n|📅|$)',
            r'car\s*model\s*[:\-]?\s*([a-zA-Z0-9\s]+?)(?:\n|$)',
            r'model\s*[:\-]?\s*([a-zA-Z0-9\s]+?)(?:\n|$)',
        ]
        
        if not result['model']:
            for pattern in model_patterns:
                matches = re.findall(pattern, text_lower)
                if matches:
                    model = matches[0].strip()
                    # Check if it's a valid model for the manufacturer
                    if result['manufacturer']:
                        mfg_key = result['manufacturer'].lower()
                        if mfg_key in self.car_manufacturers:
                            for valid_model in self.car_manufacturers[mfg_key]:
                                if valid_model.lower() in model.lower():
                                    result['model'] = valid_model.title()
                                    break
                if not result['model']:
                    result['model'] = model.strip().title()
                break
        
        # If no explicit manufacturer found, try to infer from context
        if not result['manufacturer']:
            for mfg, models in self.car_manufacturers.items():
                if mfg in text_lower:
                    result['manufacturer'] = mfg.title()
                    # Try to find corresponding model
                    if not result['model']:
                        for model in models:
                            if model in text_lower:
                                result['model'] = model.title()
                                break
                    break
        
        return result
    
    def _extract_service_type(self, text: str) -> Optional[str]:
        """Extract service type from text"""
        text_lower = text.lower()
        
        # Look for service type patterns (including emoji patterns)
        service_patterns = [
            r'🔧\s*Service\s*Type\s*[:\-]?\s*([a-zA-Z\s]+?)(?:\n|📅|$)',
            r'🔧\s*Service\s*[:\-]?\s*([a-zA-Z\s]+?)(?:\n|📅|$)',
            r'service\s*type\s*[:\-]?\s*([a-zA-Z\s]+?)(?:\n|$)',
            r'service\s*[:\-]?\s*([a-zA-Z\s]+?)(?:\n|$)',
            r'type\s*[:\-]?\s*([a-zA-Z\s]+?)(?:\n|$)',
        ]
        
        for pattern in service_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                service = matches[0].strip()
                # Handle "Not specified" case
                if 'not specified' in service:
                    continue
                for key, value in self.service_types.items():
                    if key in service:
                        return value
        
        # If no explicit service type found, try to infer from context
        for key, value in self.service_types.items():
            if key in text_lower:
                return value
        
        return None
    
    def _extract_pickup_type(self, text: str) -> Optional[str]:
        """Extract pickup type from text"""
        text_lower = text.lower()
        
        # Look for pickup type patterns
        pickup_patterns = [
            r'pnd\s*or\s*walkin\s*[:\-]?\s*([a-zA-Z\s\-]+)',
            r'pickup\s*type\s*[:\-]?\s*([a-zA-Z\s\-]+)',
            r'pickup\s*[:\-]?\s*([a-zA-Z\s\-]+)',
        ]
        
        for pattern in pickup_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                pickup = matches[0].strip()
                for key, value in self.pickup_types.items():
                    if key in pickup:
                        return value
        
        # If no explicit pickup type found, try to infer from context
        for key, value in self.pickup_types.items():
            if key in text_lower:
                return value
        
        return None
    
    def _extract_scheduled_date(self, text: str) -> Optional[str]:
        """Extract scheduled date from text"""
        text_lower = text.lower()
        
        # Look for date patterns (including emoji patterns)
        date_patterns = [
            r'📅\s*Preferred\s*Date\s*[:\-]?\s*([a-zA-Z0-9\s,\-]+?)(?:\n|🔧|$)',
            r'📅\s*Service\s*Date\s*[:\-]?\s*([a-zA-Z0-9\s,\-]+?)(?:\n|⏰|$)',
            r'service\s*date\s*[:\-]?\s*([a-zA-Z0-9\s,\-]+)',
            r'scheduled\s*date\s*[:\-]?\s*([a-zA-Z0-9\s,\-]+)',
            r'preferred\s*date\s*[:\-]?\s*([a-zA-Z0-9\s,\-]+)',
            r'date\s*[:\-]?\s*([a-zA-Z0-9\s,\-]+)',
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                date_str = matches[0].strip()
                parsed = self._parse_date_string(date_str)
                if parsed:
                    return parsed
        
        # Look for common date keywords
        if 'tomorrow' in text_lower:
            tomorrow = datetime.now(ist) + timedelta(days=1)
            return tomorrow.strftime('%Y-%m-%d')
        elif 'today' in text_lower:
            today = datetime.now(ist)
            return today.strftime('%Y-%m-%d')
        elif 'next week' in text_lower:
            next_week = datetime.now(ist) + timedelta(days=7)
            return next_week.strftime('%Y-%m-%d')
        
        return None
    
    def _parse_date_string(self, date_str: str) -> Optional[str]:
        """Parse various date string formats"""
        date_str = date_str.strip()
        
        # Handle "tomorrow"
        if 'tomorrow' in date_str.lower():
            tomorrow = datetime.now(ist) + timedelta(days=1)
            return tomorrow.strftime('%Y-%m-%d')
        
        # Handle "today"
        if 'today' in date_str.lower():
            today = datetime.now(ist)
            return today.strftime('%Y-%m-%d')
        
        # Try to parse common date formats
        date_formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%d.%m.%Y',
            '%B %d, %Y',
            '%d %B %Y',
            '%d %b %Y',
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return None
    
    def _extract_source(self, text: str) -> Optional[str]:
        """Extract source from text"""
        text_lower = text.lower()
        
        # Look for source patterns
        source_patterns = [
            r'source\s*[:\-]?\s*([a-zA-Z\s]+)',
            r'from\s*[:\-]?\s*([a-zA-Z\s]+)',
        ]
        
        for pattern in source_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                source = matches[0].strip()
                for key, value in self.sources.items():
                    if key in source:
                        return value
        
        # If no explicit source found, try to infer from context
        for key, value in self.sources.items():
            if key in text_lower:
                return value
        
        return None
    
    def _extract_status(self, text: str) -> Optional[str]:
        """Extract status from text"""
        text_lower = text.lower()
        
        # Valid status values
        valid_statuses = {
            'new': 'New Lead',
            'new lead': 'New Lead',
            'needs followup': 'Needs Followup',
            'needs follow up': 'Needs Followup',
            'did not pick up': 'Did Not Pick Up',
            'didn\'t pick up': 'Did Not Pick Up',
            'confirmed': 'Confirmed',
            'open': 'Open',
            'completed': 'Completed',
            'feedback': 'Feedback',
        }
        
        # Look for status patterns (including emoji patterns)
        status_patterns = [
            r'📊\s*Status\s*[:\-]?\s*([a-zA-Z\s]+?)(?:\n|📅|$)',
            r'status\s*[:\-]?\s*([a-zA-Z\s]+?)(?:\n|$)',
        ]
        
        for pattern in status_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                status_text = matches[0].strip()
                for key, value in valid_statuses.items():
                    if key in status_text:
                        return value
        
        # If no explicit status found, try to infer from context
        for key, value in valid_statuses.items():
            if key in text_lower:
                return value
        
        return None

# Create a global instance
customer_parser = CustomerInfoParser()

def parse_customer_text(text: str) -> Dict[str, Optional[str]]:
    """Convenience function to parse customer text"""
    return customer_parser.parse_text(text) 