#!/usr/bin/env python3
"""
Test script for Gmail Divert Parser
Use this to test Gmail integration independently of the main hydrophone monitoring system.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    print("Gmail Divert Parser Test")
    print("=" * 40)
    
    try:
        from gmail_divert_parser import GmailDivertParser, setup_gmail_credentials
        
        # Check if credentials exist
        credentials_path = os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials.json')
        if not os.path.exists(credentials_path):
            print(f"❌ Gmail credentials not found at: {credentials_path}")
            print("\nSetup Instructions:")
            print(setup_gmail_credentials())
            return 1
            
        print(f"✅ Found Gmail credentials at: {credentials_path}")
        
        # Initialize parser
        print("\n📧 Initializing Gmail parser...")
        parser = GmailDivertParser(
            credentials_path=credentials_path,
            token_path=os.getenv('GMAIL_TOKEN_PATH', 'token.json')
        )
        
        # Test authentication
        print("🔐 Testing Gmail authentication...")
        if parser.authenticate():
            print("✅ Gmail authentication successful!")
        else:
            print("❌ Gmail authentication failed")
            return 1
            
        # Test email search
        print("\n🔍 Searching for divert emails...")
        messages = parser.search_divert_emails(days_back=30)
        print(f"📬 Found {len(messages)} potential divert emails")
        
        if len(messages) == 0:
            print("⚠️  No divert emails found. This might be normal if:")
            print("   - No recent divert events occurred")
            print("   - Email search criteria need adjustment")
            print("   - Gmail account doesn't have access to divert emails")
            return 0
            
        # Test parsing first few emails
        test_count = min(2, len(messages))  # Reduced to 2 for faster testing
        print(f"\n📖 Testing email parsing (first {test_count} emails)...")
        for i, message in enumerate(messages[:test_count]):
            print(f"\n--- Email {i+1} ---")
            try:
                subject, body, date = parser.get_email_content(message['id'])
                
                if subject:
                    print(f"Subject: {subject}")
                    parsed = parser.parse_divert_email(subject, body, date)
                    
                    if parsed['timestamp']:
                        print(f"Timestamp: {parsed['timestamp']}")
                    if parsed['system']:
                        print(f"System: {parsed['system']}")
                    if parsed['locations']:
                        print(f"Locations found: {len(parsed['locations'])}")
                        for location, status in parsed['locations'].items():
                            print(f"  - {location}: {status}")
                    else:
                        print("⚠️  No location data parsed from this email")
                else:
                    print("❌ Could not retrieve email content")
                    
            except Exception as e:
                print(f"❌ Error processing email {i+1}: {e}")
                print("Continuing with next email...")
                
        # Test full status update
        print(f"\n🔄 Testing full divert status update...")
        current_status = parser.update_divert_status(days_back=7)
        
        # Print summary
        summary = parser.get_divert_summary()
        print(f"\n📊 Divert Status Summary:")
        print(f"   Total locations monitored: {summary['total_monitored']}")
        print(f"   Currently diverted: {summary['currently_diverted']}")
        print(f"   Currently bypass: {summary['currently_bypass']}")
        print(f"   Events processed: {summary['events_processed']}")
        print(f"   Last updated: {summary['last_updated']}")
        
        # Show current divert status
        if current_status:
            print(f"\n🎯 Current Divert Status:")
            for location, info in current_status.items():
                print(f"   {location}: {info['status']} (since {info['timestamp']})")
        else:
            print(f"\n✅ No locations currently diverted")
            
        # Test location queries
        print(f"\n🧪 Testing location queries...")
        test_locations = ['BACUS', 'BIIP', 'BACNH.H1']  # Add your actual location codes
        
        for location in test_locations:
            divert_info = parser.get_location_divert_info(location)
            is_diverted = parser.is_location_diverted(location)
            
            if divert_info:
                print(f"   {location}: {divert_info['status']} (since {divert_info['timestamp']})")
            else:
                print(f"   {location}: No divert status")
                
        # Test divert period analysis
        from datetime import timedelta
        print(f"\n📈 Testing divert period analysis...")
        print("=" * 50)
        print("DIVERT PERIODS ANALYSIS")
        print("=" * 50)
        
        # Test period retrieval for a specific location
        test_location = test_locations[0] if test_locations else 'BACNH.H1'
        periods = parser.get_divert_periods(test_location)
        print(f"\n📊 Divert periods for {test_location}:")
        if periods:
            for i, period in enumerate(periods):
                status = period['status']
                start = period['start'].strftime('%Y-%m-%d %H:%M')
                end = period['end'].strftime('%Y-%m-%d %H:%M') if period['end'] else 'Ongoing'
                duration = period['duration']
                system = period['system']
                print(f"   Period {i+1}: {status} | {start} → {end} | Duration: {duration} | System: {system}")
        else:
            print(f"   No periods found for {test_location}")
        
        # Test statistics for the last week
        start_date = datetime.now() - timedelta(days=7)
        stats = parser.get_divert_statistics(test_location, start_date=start_date)
        print(f"\n📈 Statistics for {test_location} (last 7 days):")
        print(f"   Total periods: {stats['total_periods']}")
        print(f"   Divert events: {stats['divert_events']}")
        print(f"   Bypass events: {stats['bypass_events']}")
        print(f"   Time diverted: {stats['divert_time']}")
        print(f"   Time in bypass: {stats['bypass_time']}")
        print(f"   Divert percentage: {stats['divert_percentage']:.1f}%")
        print(f"   Bypass percentage: {stats['bypass_percentage']:.1f}%")
        
        # Show all locations with recent divert activity
        all_periods = parser.get_all_divert_periods(start_date=start_date)
        print(f"\n🌐 Locations with divert activity (last 7 days): {len(all_periods)}")
        for location, location_periods in all_periods.items():
            recent_divert_periods = [p for p in location_periods if p['status'] == 'Divert']
            if recent_divert_periods:
                total_divert_time = sum((p['duration'] for p in recent_divert_periods), timedelta())
                print(f"   {location}: {len(recent_divert_periods)} divert periods, {total_divert_time} total diverted time")
                
        print(f"\n✅ Gmail divert parser test completed successfully!")
        return 0
        
    except ImportError as e:
        print(f"❌ Cannot import Gmail parser: {e}")
        print("Install dependencies with: pip install -r requirements.txt")
        return 1
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 