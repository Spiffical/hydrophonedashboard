"""
Gmail Divert Parser for Hydrophone Monitoring
Parses divert status emails to understand when hydrophones are intentionally
not collecting data due to diversions.
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

# Import location mappings from config module
from ..config.location_mappings import LOCATION_MAPPING

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

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
        
        # Parse body for location status information
        # Look for "New Switch Line-Up:" section
        if 'New Switch Line-Up:' in body:
            try:
                # Find the section after "New Switch Line-Up:"
                lineup_start = body.find('New Switch Line-Up:')
                if lineup_start != -1:
                    # Get text after the lineup section
                    lineup_section = body[lineup_start:]
                    
                    # Stop parsing at lines with many underscores/dashes (separators)
                    lines = lineup_section.split('\n')
                    relevant_lines = []
                    
                    for line in lines[1:]:  # Skip the "New Switch Line-Up:" line itself
                        # Stop if we hit a separator line
                        if len(line) > 20 and (line.count('_') > 10 or line.count('-') > 10):
                            break
                        relevant_lines.append(line)
                    
                    # Join back and process
                    relevant_text = '\n'.join(relevant_lines)
                    
                    # Look for patterns like:
                    # SoG_East: Bypass
                    # SoG_Delta: Divert
                    # [1] Barkley Cnyn: Divert
                    location_patterns = [
                        r'([A-Za-z0-9_\[\]\s]+):\s*(Bypass|Divert)',
                        r'(\[[0-9]+\]\s*[A-Za-z0-9_\s]+):\s*(Bypass|Divert)',
                    ]
                    
                    for pattern in location_patterns:
                        matches = re.finditer(pattern, relevant_text, re.MULTILINE | re.IGNORECASE)
                        for match in matches:
                            location = match.group(1).strip()
                            status = match.group(2).strip()
                            parsed_info['locations'][location] = status
                            
            except Exception as e:
                print(f"Error parsing body: {e}")
                # Don't fail completely, just log the error
                pass
        
        return parsed_info
    
    def map_locations_to_hydrophones(self, email_locations):
        """
        Map email location names to hydrophone location codes.
        
        Args:
            email_locations: Dict of {location_name: status}
            
        Returns:
            Dict of {hydrophone_code: status}
        """
        hydrophone_status = {}
        
        for email_location, status in email_locations.items():
            # Look up in LOCATION_MAPPING
            hydrophone_codes = LOCATION_MAPPING.get(email_location, [])
            
            for code in hydrophone_codes:
                hydrophone_status[code] = status
                
        return hydrophone_status
    
    def update_divert_status(self, days_back=7):
        """
        Update divert status by parsing recent emails.
        
        Args:
            days_back: Number of days to search back
            
        Returns:
            Dict with updated status information
        """
        if not self.service:
            self.authenticate()
            
        # Search for divert emails
        messages = self.search_divert_emails(days_back)
        
        parsed_emails = []
        
        for message in messages:
            message_id = message['id']
            subject, body, date = self.get_email_content(message_id)
            
            if subject and ('[Divert]' in subject or 'DDS' in subject):
                parsed_info = self.parse_divert_email(subject, body, date)
                if parsed_info['locations']:  # Only include if we found locations
                    parsed_emails.append(parsed_info)
        
        # Sort by timestamp (newest first)
        parsed_emails.sort(key=lambda x: x['timestamp'] or datetime.min, reverse=True)
        
        # Update current status based on most recent info per location
        self.current_divert_status = {}
        location_timestamps = {}
        
        for email_info in parsed_emails:
            email_locations = email_info['locations']
            timestamp = email_info['timestamp']
            system = email_info['system']
            
            # Map email locations to hydrophone codes
            hydrophone_status = self.map_locations_to_hydrophones(email_locations)
            
            for hydrophone_code, status in hydrophone_status.items():
                # Only update if this is newer than what we have
                if (hydrophone_code not in location_timestamps or 
                    (timestamp and timestamp > location_timestamps[hydrophone_code])):
                    
                    self.current_divert_status[hydrophone_code] = {
                        'status': status,
                        'timestamp': timestamp,
                        'system': system
                    }
                    location_timestamps[hydrophone_code] = timestamp
        
        # Store parsed emails for history
        self.divert_history = parsed_emails
        
        # Calculate historical periods
        self._calculate_divert_periods()
        
        return {
            'emails_processed': len(parsed_emails),
            'hydrophones_with_status': len(self.current_divert_status),
            'current_divert_count': len([s for s in self.current_divert_status.values() if s['status'] == 'Divert']),
            'current_bypass_count': len([s for s in self.current_divert_status.values() if s['status'] == 'Bypass']),
        }
    
    def get_location_divert_info(self, location_code):
        """
        Get divert information for a specific location.
        
        Args:
            location_code: Hydrophone location code (e.g., 'CBCH.H1')
            
        Returns:
            Dict with divert info or None if no information available
        """
        return self.current_divert_status.get(location_code)
    
    def is_location_diverted(self, location_code):
        """
        Check if a location is currently diverted.
        
        Args:
            location_code: Hydrophone location code
            
        Returns:
            bool: True if location is diverted
        """
        info = self.get_location_divert_info(location_code)
        return info is not None and info['status'] == 'Divert'
    
    def get_divert_summary(self):
        """
        Get a summary of current divert status.
        
        Returns:
            Dict with summary statistics
        """
        total_monitored = len(self.current_divert_status)
        currently_diverted = len([s for s in self.current_divert_status.values() if s['status'] == 'Divert'])
        currently_bypass = len([s for s in self.current_divert_status.values() if s['status'] == 'Bypass'])
        events_processed = len(self.divert_history)
        
        return {
            'total_monitored': total_monitored,
            'currently_diverted': currently_diverted,
            'currently_bypass': currently_bypass,
            'events_processed': events_processed
        }
    
    def _calculate_divert_periods(self):
        """Calculate historical divert periods from parsed emails."""
        # Group events by location and sort by timestamp
        location_events = {}
        
        for email_info in self.divert_history:
            if not email_info['timestamp']:
                continue
                
            email_locations = email_info['locations']
            hydrophone_status = self.map_locations_to_hydrophones(email_locations)
            
            for location, status in hydrophone_status.items():
                if location not in location_events:
                    location_events[location] = []
                    
                location_events[location].append({
                    'timestamp': email_info['timestamp'],
                    'status': status,
                    'system': email_info['system']
                })
        
        # Sort events by timestamp for each location
        for location in location_events:
            location_events[location].sort(key=lambda x: x['timestamp'])
        
        # Calculate periods for each location
        self.divert_periods = {}
        
        for location, events in location_events.items():
            periods = []
            current_period = None
            
            for event in events:
                if current_period is None:
                    # Start new period
                    current_period = {
                        'start': event['timestamp'],
                        'end': None,
                        'status': event['status'],
                        'system': event['system']
                    }
                elif current_period['status'] != event['status']:
                    # Status changed, close current period and start new one
                    current_period['end'] = event['timestamp']
                    periods.append(current_period)
                    
                    current_period = {
                        'start': event['timestamp'],
                        'end': None,
                        'status': event['status'],
                        'system': event['system']
                    }
                # If status is the same, just update the current period timestamp
                # (end time will be set when status changes or period ends)
            
            # Add final period if exists
            if current_period:
                periods.append(current_period)
            
            self.divert_periods[location] = periods
    
    def get_divert_periods(self, location_code, start_date=None, end_date=None):
        """
        Get divert periods for a specific location within a date range.
        
        Args:
            location_code: Hydrophone location code
            start_date: Start date filter (datetime object, optional)
            end_date: End date filter (datetime object, optional)
            
        Returns:
            List of divert periods
        """
        periods = self.divert_periods.get(location_code, [])
        
        if start_date or end_date:
            filtered_periods = []
            for period in periods:
                period_start = period['start']
                period_end = period['end'] or datetime.now()
                
                # Check if period overlaps with requested range
                if start_date and period_end < start_date:
                    continue
                if end_date and period_start > end_date:
                    continue
                    
                filtered_periods.append(period)
            return filtered_periods
        
        return periods
    
    def get_divert_statistics(self, location_code, start_date=None, end_date=None):
        """
        Get divert statistics for a location within a date range.
        
        Args:
            location_code: Hydrophone location code
            start_date: Start date filter (datetime object, optional)
            end_date: End date filter (datetime object, optional)
            
        Returns:
            Dict with statistics
        """
        periods = self.get_divert_periods(location_code, start_date, end_date)
        
        total_divert_time = timedelta()
        total_bypass_time = timedelta()
        divert_periods_count = 0
        bypass_periods_count = 0
        
        analysis_start = start_date or (min(p['start'] for p in periods) if periods else datetime.now())
        analysis_end = end_date or datetime.now()
        
        for period in periods:
            period_start = max(period['start'], analysis_start)
            period_end = min(period['end'] or datetime.now(), analysis_end)
            
            if period_end <= period_start:
                continue
                
            duration = period_end - period_start
            
            if period['status'] == 'Divert':
                total_divert_time += duration
                divert_periods_count += 1
            elif period['status'] == 'Bypass':
                total_bypass_time += duration
                bypass_periods_count += 1
        
        total_analysis_time = analysis_end - analysis_start
        
        return {
            'location_code': location_code,
            'analysis_start': analysis_start,
            'analysis_end': analysis_end,
            'total_analysis_time': total_analysis_time,
            'total_divert_time': total_divert_time,
            'total_bypass_time': total_bypass_time,
            'divert_percentage': (total_divert_time.total_seconds() / total_analysis_time.total_seconds() * 100) if total_analysis_time.total_seconds() > 0 else 0,
            'bypass_percentage': (total_bypass_time.total_seconds() / total_analysis_time.total_seconds() * 100) if total_analysis_time.total_seconds() > 0 else 0,
            'divert_periods_count': divert_periods_count,
            'bypass_periods_count': bypass_periods_count,
            'total_periods': len(periods)
        }
    
    def get_all_divert_periods(self, start_date=None, end_date=None):
        """
        Get all divert periods across all monitored locations.
        
        Args:
            start_date: Start date filter (datetime object, optional)
            end_date: End date filter (datetime object, optional)
            
        Returns:
            Dict of {location_code: [periods]}
        """
        all_periods = {}
        
        for location_code in self.divert_periods:
            periods = self.get_divert_periods(location_code, start_date, end_date)
            if periods:
                all_periods[location_code] = periods
                
        return all_periods

def setup_gmail_credentials():
    """
    Interactive setup for Gmail API credentials.
    Run this function to set up Gmail access for the first time.
    """
    print("Gmail API Setup for Hydrophone Divert Monitoring")
    print("=" * 50)
    print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
    print("2. Create a new project or select an existing one")
    print("3. Enable the Gmail API")
    print("4. Create credentials (OAuth 2.0 Client ID)")
    print("5. Download the credentials JSON file")
    print("6. Save it as 'credentials.json' in your project directory")
    print("7. Run your divert parser - it will open a browser for authorization")
    print("\nDetailed instructions: https://developers.google.com/gmail/api/quickstart/python")

if __name__ == "__main__":
    # Test the parser
    parser = GmailDivertParser()
    try:
        parser.authenticate()
        status = parser.update_divert_status(days_back=7)
        print("Divert status update completed:")
        print(f"  - Emails processed: {status['emails_processed']}")
        hydrophone_word = 'Hydrophone' if status['hydrophones_with_status'] == 1 else 'Hydrophones'
        print(f"  - {hydrophone_word} monitored: {status['hydrophones_with_status']}")
        print(f"  - Currently diverted: {status['current_divert_count']}")
        print(f"  - Currently bypass: {status['current_bypass_count']}")
        
        summary = parser.get_divert_summary()
        print(f"\nSummary: {summary}")
        
    except FileNotFoundError:
        print("Gmail credentials not found. Run setup_gmail_credentials() first.")
    except Exception as e:
        print(f"Error: {e}")
        setup_gmail_credentials() 