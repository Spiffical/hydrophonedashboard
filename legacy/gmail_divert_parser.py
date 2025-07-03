"""
Gmail Divert Parser for Hydrophone Monitoring
Parses divert status emails to understand when hydrophones are intentionally
not collecting data due to intelligence diversions.
"""

import os
import json
import re
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
import logging

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Location mapping - maps email location names to hydrophone location codes
# Based on actual ONC hydrophone deployments and divert system naming
LOCATION_MAPPING = {
    # SoG DDS system locations
    'SoG_East': ['ECHO3.H1', 'ECHO3.H2', 'ECHO3.H3', 'ECHO3.H4'],  # SoG East = ECHO3 array
    'SoG_Delta': ['CBCH.H1', 'CBCH.H2', 'CBCH.H3', 'CBCH.H4'],    # SoG Delta = Cascadia Basin array
    'SoG_Central': ['PSGCH.H1', 'PSGCH.H3'],  # SoG Central = PSGCH array (only H1 and H3 active)
    
    # Saanich DDS system locations  
    'Saanich_Inlet': ['PVIPH.H1', 'PVIPH.H3'],  # Saanich Inlet = PVIPH array (only H1 and H3 active)
    
    # NC-DDS system locations - with bracket format
    '[1] Barkley Cnyn': ['BACNH.H1', 'BACNH.H2', 'BACNH.H3', 'BACNH.H4', 'BACUS'],  # Barkley Canyon (main array + upper slope)
    '[2] ODP 1027': ['CBCH.H1', 'CBCH.H2', 'CBCH.H3', 'CBCH.H4'],   # ODP 1027C = Cascadia Basin (CBCH)
    '[3] Endeavour': ['KEMFH.H1', 'KEMFH.H2', 'KEMFH.H3', 'KEMFH.H4'],  # Endeavour = KEMFH array
    '[4] ODP 889': [],    # ODP 889 - need to identify corresponding ONC location code  
    '[5] Folger Pass': ['FGPD'],  # Folger Pass = Folger Deep
    
    # Additional ODP sites discovered
    'ODP 1364A': ['CQSH.H1', 'CQSH.H2', 'CQSH.H3', 'CQSH.H4'],  # ODP 1364A = Clayoquot Slope (CQSH)
    'ODP 1026': ['NC27.H3', 'NC27.H4'],  # ODP 1026 = NC27 array (only H3 and H4 active)
    
    # NC-DDS system locations - without bracket format (fallback)
    'Barkley Cnyn': ['BACNH.H1', 'BACNH.H2', 'BACNH.H3', 'BACNH.H4', 'BACUS'],  # Barkley Canyon (main array + upper slope)
    'ODP 1027': ['CBCH.H1', 'CBCH.H2', 'CBCH.H3', 'CBCH.H4'],   # ODP 1027C = Cascadia Basin (CBCH)
    'Endeavour': ['KEMFH.H1', 'KEMFH.H2', 'KEMFH.H3', 'KEMFH.H4'],  # Endeavour = KEMFH array
    'ODP 889': [],    # ODP 889 - need to identify corresponding ONC location code
    'Folger Pass': ['FGPD'],  # Folger Pass = Folger Deep
    
    # Additional mappings for completeness (if these locations appear in emails)
    'Burrard Inlet': ['BIIP'],  # Burrard Inlet
    'Cambridge Bay': ['CBYIP'],  # Cambridge Bay 
    'China Creek': ['CCIP'],   # China Creek
    'Clayoquot Slope': ['CQSH.H1', 'CQSH.H2', 'CQSH.H3', 'CQSH.H4'],  # Clayoquot Slope array (ODP 1364A)
    'Digby Island': ['DIIP'],  # Digby Island
    'Hartley Bay': ['HBIP'],   # Hartley Bay
    'Holyrood Bay': ['HRBIP'],  # Holyrood Bay / Conception Bay
    'Kitamaat Village': ['KVIP'],  # Kitamaat Village
}

class GmailDivertParser:
    """Parses Gmail emails to extract divert status information for hydrophones."""
    
    def __init__(self, credentials_path='credentials.json', token_path='token.json'):
        """
        Initialize the Gmail API client.
        
        Args:
            credentials_path: Path to Gmail API credentials file
            token_path: Path to store/retrieve access tokens
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.divert_history = []
        self.current_divert_status = {}
        
        # Historical divert periods tracking
        self.divert_periods = {}  # location -> [{'start': datetime, 'end': datetime, 'system': str, 'status': str}, ...]
        
    def authenticate(self):
        """Authenticate with Gmail API using OAuth2."""
        creds = None
        
        # Load existing token if it exists
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            
        # If there are no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Gmail credentials file not found at {self.credentials_path}. "
                        "Please download it from Google Cloud Console."
                    )
                    
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
            # Save credentials for next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
                
        self.service = build('gmail', 'v1', credentials=creds)
        return True
        
    def search_divert_emails(self, days_back=30):
        """
        Search for divert emails in the last N days.
        
        Args:
            days_back: Number of days to search back
            
        Returns:
            List of email message IDs
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Format dates for Gmail search (YYYY/MM/DD)
            start_date_str = start_date.strftime('%Y/%m/%d')
            
            # Gmail search query for divert emails
            query = f'subject:"[Divert]" OR subject:"DDS" after:{start_date_str}'
            
            result = self.service.users().messages().list(
                userId='me', 
                q=query,
                maxResults=500  # Adjust as needed
            ).execute()
            
            messages = result.get('messages', [])
            
            print(f"Found {len(messages)} potential divert emails in the last {days_back} days")
            return messages
            
        except HttpError as error:
            print(f"Gmail API error: {error}")
            return []
            
    def get_email_content(self, message_id):
        """
        Get the content of a specific email.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Tuple of (subject, body, date)
        """
        try:
            message = self.service.users().messages().get(
                userId='me', 
                id=message_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = message['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            # Extract body
            body = ''
            payload = message.get('payload', {})
            
            if 'parts' in payload:
                for i, part in enumerate(payload['parts']):
                    part_size = part.get('body', {}).get('size', 0)
                    
                    # Skip very large parts (likely attachments)
                    if part_size > 1000000:  # 1MB limit
                        continue
                        
                    if part['mimeType'] == 'text/plain':
                        data = part['body'].get('data', '')
                        if data:
                            try:
                                body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                                break
                            except Exception:
                                continue
                
                # If no text/plain found, try text/html as fallback
                if not body:
                    for i, part in enumerate(payload['parts']):
                        if part['mimeType'] == 'text/html' and part.get('body', {}).get('size', 0) < 1000000:
                            data = part['body'].get('data', '')
                            if data:
                                try:
                                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                                    break
                                except Exception:
                                    continue
            else:
                if payload.get('mimeType') == 'text/plain':
                    data = payload.get('body', {}).get('data', '')
                    if data:
                        try:
                            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        except Exception:
                            pass
                    
            return subject, body, date
            
        except HttpError as error:
            print(f"Error retrieving email {message_id}: {error}")
            return '', '', ''
            
    def parse_divert_email(self, subject, body, date_str):
        """
        Parse a divert email to extract status information.
        
        Args:
            subject: Email subject
            body: Email body
            date_str: Email date string
            
        Returns:
            Dict with parsed divert information
        """
        parsed_info = {
            'timestamp': None,
            'system': None,
            'locations': {},  # location -> status mapping
            'raw_subject': subject,
            'raw_body': body
        }
        
        # Parse timestamp from subject (format: 2025_07_01 14:44)
        timestamp_match = re.search(r'(\d{4}_\d{2}_\d{2}\s+\d{2}:\d{2})', subject)
        if timestamp_match:
            try:
                timestamp_str = timestamp_match.group(1).replace('_', '-')
                parsed_info['timestamp'] = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M')
            except ValueError as e:
                pass
                
        # Extract system type (SoG DDS, NC-DDS, etc.)
        if 'SoG DDS' in subject:
            parsed_info['system'] = 'SoG DDS'
        elif 'NC-DDS' in subject:
            parsed_info['system'] = 'NC-DDS'
        elif 'Saanich DDS' in subject:
            parsed_info['system'] = 'Saanich DDS'
            
        # Parse location statuses from body
        # Look for "New Switch Line-Up:" section
        if 'New Switch Line-Up:' in body:
            lines = body.split('\n')
            in_lineup_section = False
            
            for line_num, line in enumerate(lines):
                line = line.strip()
                
                if 'New Switch Line-Up:' in line:
                    in_lineup_section = True
                    continue
                    
                if in_lineup_section:
                    # Stop at separator or new section
                    if (line.startswith('---') or 
                        line.startswith('___') or 
                        line.startswith('===') or
                        'mailing list' in line.lower() or
                        line.count('_') > 20 or  # Lines with many underscores
                        line.count('-') > 20):   # Lines with many dashes
                        break
                    
                    # Skip empty lines
                    if not line:
                        continue
                        
                    # Parse location status lines
                    # Format examples:
                    # "SoG_East: Divert"
                    # "[1] Barkley Cnyn: Divert"
                    # "[2] ODP 1027: Bypass"
                    
                    # Try different patterns
                    patterns = [
                        r'^([^:]+):\s*(Divert|Bypass)$',  # "Location: Status"
                        r'^\[\d+\]\s*([^:]+):\s*(Divert|Bypass)$',  # "[1] Location: Status"
                        r'^(\w+(?:_\w+)*):\s*(Divert|Bypass)$'  # "Location_Name: Status"
                    ]
                    
                    for pattern in patterns:
                        match = re.match(pattern, line)
                        if match:
                            location = match.group(1).strip()
                            status = match.group(2).strip()
                            parsed_info['locations'][location] = status
                            break
        return parsed_info
        
    def map_locations_to_hydrophones(self, email_locations):
        """
        Map email location names to hydrophone location codes.
        
        Args:
            email_locations: Dict of email location -> status
            
        Returns:
            Dict of hydrophone location codes -> status
        """
        hydrophone_status = {}
        
        for email_location, status in email_locations.items():
            if email_location in LOCATION_MAPPING:
                for hydrophone_code in LOCATION_MAPPING[email_location]:
                    hydrophone_status[hydrophone_code] = status
            else:
                # Log unmapped locations for future mapping
                print(f"Warning: Unmapped location in email: '{email_location}'")
                
        return hydrophone_status
        
    def update_divert_status(self, days_back=7):
        """
        Update current divert status by parsing recent emails.
        
        Args:
            days_back: How many days back to check for emails
            
        Returns:
            Dict of current divert status for each location
        """
        if not self.service:
            if not self.authenticate():
                return {}
                
        print(f"Checking for divert emails in the last {days_back} days...")
        
        # Get recent emails
        messages = self.search_divert_emails(days_back)
        
        # Parse each email and build history
        divert_events = []
        
        for message in messages:
            subject, body, date_str = self.get_email_content(message['id'])
            
            # Only process if it looks like a divert email
            if '[Divert]' in subject or 'Mode Change' in subject:
                parsed = self.parse_divert_email(subject, body, date_str)
                
                if parsed['timestamp'] and parsed['locations']:
                    # Map to hydrophone codes
                    hydrophone_status = self.map_locations_to_hydrophones(parsed['locations'])
                    
                    event = {
                        'timestamp': parsed['timestamp'],
                        'system': parsed['system'],
                        'locations': hydrophone_status,
                        'email_subject': subject
                    }
                    
                    divert_events.append(event)
                    print(f"  Parsed: {parsed['timestamp']} - {len(hydrophone_status)} locations")
                    
        # Sort events by timestamp (newest first)
        divert_events.sort(key=lambda x: x['timestamp'], reverse=True)
        self.divert_history = divert_events
        
        # Calculate current status (most recent status for each location)
        current_status = {}
        
        for event in reversed(divert_events):  # Process oldest to newest
            for location, status in event['locations'].items():
                current_status[location] = {
                    'status': status,
                    'timestamp': event['timestamp'],
                    'system': event['system']
                }
                
        self.current_divert_status = current_status
        
        # Calculate divert periods from the event history
        self._calculate_divert_periods()
        
        print(f"Current divert status covers {len(current_status)} locations")
        return current_status
        
    def get_location_divert_info(self, location_code):
        """
        Get divert information for a specific location.
        
        Args:
            location_code: Hydrophone location code
            
        Returns:
            Dict with divert status info or None if not in divert
        """
        if location_code in self.current_divert_status:
            return self.current_divert_status[location_code]
        return None
        
    def is_location_diverted(self, location_code):
        """
        Check if a location is currently diverted.
        
        Args:
            location_code: Hydrophone location code
            
        Returns:
            Boolean indicating if location is in divert mode
        """
        divert_info = self.get_location_divert_info(location_code)
        return divert_info and divert_info['status'] == 'Divert'
        
    def get_divert_summary(self):
        """
        Get a summary of current divert status.
        
        Returns:
            Dict with summary statistics
        """
        total_locations = len(self.current_divert_status)
        diverted_count = sum(1 for info in self.current_divert_status.values() 
                           if info['status'] == 'Divert')
        bypass_count = total_locations - diverted_count
        
        return {
            'total_monitored': total_locations,
            'currently_diverted': diverted_count,
            'currently_bypass': bypass_count,
            'last_updated': datetime.now(),
            'events_processed': len(self.divert_history)
        }
    
    def _calculate_divert_periods(self):
        """
        Calculate divert periods from the event history.
        Creates start/end periods for each location's divert status.
        """
        self.divert_periods = {}
        
        # Sort events by timestamp (oldest first for chronological processing)
        sorted_events = sorted(self.divert_history, key=lambda x: x['timestamp'])
        
        # Track state for each location
        location_states = {}  # location -> {'status': str, 'start_time': datetime, 'system': str}
        
        for event in sorted_events:
            for location, status in event['locations'].items():
                
                # Initialize location if first time seeing it
                if location not in location_states:
                    location_states[location] = {
                        'status': status,
                        'start_time': event['timestamp'],
                        'system': event['system']
                    }
                    if location not in self.divert_periods:
                        self.divert_periods[location] = []
                    continue
                
                # Check if status changed
                if location_states[location]['status'] != status:
                    # Close previous period
                    prev_state = location_states[location]
                    period = {
                        'start': prev_state['start_time'],
                        'end': event['timestamp'],
                        'status': prev_state['status'],
                        'system': prev_state['system'],
                        'duration': event['timestamp'] - prev_state['start_time']
                    }
                    self.divert_periods[location].append(period)
                    
                    # Start new period
                    location_states[location] = {
                        'status': status,
                        'start_time': event['timestamp'],
                        'system': event['system']
                    }
        
        # Close any open periods (ongoing status)
        current_time = datetime.now()
        for location, state in location_states.items():
            if location in self.divert_periods:
                # Add ongoing period
                period = {
                    'start': state['start_time'],
                    'end': None,  # Ongoing
                    'status': state['status'],
                    'system': state['system'],
                    'duration': current_time - state['start_time']
                }
                self.divert_periods[location].append(period)
    
    def get_divert_periods(self, location_code, start_date=None, end_date=None):
        """
        Get all divert periods for a specific location within a timeframe.
        
        Args:
            location_code: Hydrophone location code
            start_date: Optional start date filter (datetime)
            end_date: Optional end date filter (datetime)
            
        Returns:
            List of divert periods with start/end times and status
        """
        if location_code not in self.divert_periods:
            return []
        
        periods = self.divert_periods[location_code]
        
        # Filter by date range if specified
        if start_date or end_date:
            filtered_periods = []
            for period in periods:
                # Check if period overlaps with requested timeframe
                period_start = period['start']
                period_end = period['end'] or datetime.now()
                
                # Skip if period ends before our start date
                if start_date and period_end < start_date:
                    continue
                    
                # Skip if period starts after our end date
                if end_date and period_start > end_date:
                    continue
                    
                filtered_periods.append(period)
            return filtered_periods
        
        return periods
    
    def get_divert_statistics(self, location_code, start_date=None, end_date=None):
        """
        Get divert statistics for a location within a timeframe.
        
        Args:
            location_code: Hydrophone location code
            start_date: Optional start date filter (datetime)
            end_date: Optional end date filter (datetime)
            
        Returns:
            Dict with divert statistics
        """
        periods = self.get_divert_periods(location_code, start_date, end_date)
        
        total_time = timedelta()
        divert_time = timedelta()
        bypass_time = timedelta()
        divert_events = 0
        bypass_events = 0
        
        # Calculate timeframe
        if start_date and end_date:
            total_time = end_date - start_date
        elif periods:
            # Use full range of periods
            earliest = min(p['start'] for p in periods)
            latest = max(p['end'] or datetime.now() for p in periods)
            total_time = latest - earliest
        
        # Sum up periods by status
        for period in periods:
            duration = period['duration']
            if period['status'] == 'Divert':
                divert_time += duration
                divert_events += 1
            elif period['status'] == 'Bypass':
                bypass_time += duration
                bypass_events += 1
        
        # Calculate percentages
        divert_percentage = (divert_time.total_seconds() / total_time.total_seconds() * 100) if total_time.total_seconds() > 0 else 0
        bypass_percentage = (bypass_time.total_seconds() / total_time.total_seconds() * 100) if total_time.total_seconds() > 0 else 0
        
        return {
            'location': location_code,
            'total_periods': len(periods),
            'divert_events': divert_events,
            'bypass_events': bypass_events,
            'total_time': total_time,
            'divert_time': divert_time,
            'bypass_time': bypass_time,
            'divert_percentage': divert_percentage,
            'bypass_percentage': bypass_percentage,
            'timeframe_start': start_date,
            'timeframe_end': end_date
        }
    
    def get_all_divert_periods(self, start_date=None, end_date=None):
        """
        Get divert periods for all locations within a timeframe.
        
        Args:
            start_date: Optional start date filter (datetime)
            end_date: Optional end date filter (datetime)
            
        Returns:
            Dict of location -> list of periods
        """
        all_periods = {}
        for location in self.divert_periods.keys():
            periods = self.get_divert_periods(location, start_date, end_date)
            if periods:  # Only include locations with periods in the timeframe
                all_periods[location] = periods
        return all_periods

def setup_gmail_credentials():
    """
    Provide instructions for setting up Gmail credentials.
    """
    instructions = """
    To set up Gmail API access for divert monitoring:
    
    1. Go to Google Cloud Console (console.cloud.google.com)
    2. Create a new project or select existing one
    3. Enable the Gmail API
    4. Create credentials (OAuth 2.0 client ID) for desktop application
    5. Download the credentials file as 'credentials.json' in this directory
    6. Update your .env file with:
       GMAIL_CREDENTIALS_PATH=credentials.json
       GMAIL_TOKEN_PATH=token.json
       
    The first time you run this, it will open a browser for OAuth consent.
    """
    return instructions

if __name__ == "__main__":
    # Test the Gmail parser
    print("Testing Gmail Divert Parser...")
    
    try:
        parser = GmailDivertParser()
        
        # Check if credentials exist
        if not os.path.exists('credentials.json'):
            print("Gmail credentials not found.")
            print(setup_gmail_credentials())
        else:
            # Test authentication and parsing
            if parser.authenticate():
                print("Gmail authentication successful!")
                
                # Get recent divert status
                status = parser.update_divert_status(days_back=7)
                
                # Print summary
                summary = parser.get_divert_summary()
                print(f"\nDivert Summary:")
                print(f"  Total locations monitored: {summary['total_monitored']}")
                print(f"  Currently diverted: {summary['currently_diverted']}")
                print(f"  Currently bypass: {summary['currently_bypass']}")
                print(f"  Events processed: {summary['events_processed']}")
                
                # Show current status
                if status:
                    print(f"\nCurrent Divert Status:")
                    for location, info in status.items():
                        print(f"  {location}: {info['status']} (since {info['timestamp']})")
                        
    except Exception as e:
        print(f"Error testing Gmail parser: {e}")
        print("\nTo set up Gmail access:")
        print(setup_gmail_credentials()) 