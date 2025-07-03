#!/usr/bin/env python3
"""
Location Mapping Setup Tool
Helps verify and correct the mapping between divert email locations and actual hydrophone location codes.
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def extract_hydrophone_locations():
    """Extract actual hydrophone location codes from the dashboard HTML."""
    try:
        with open('Hydrophone.html', 'r') as f:
            content = f.read()
        
        # Extract location codes from the HTML structure
        import re
        # Look for patterns like <span>Site</span>LOCATION_CODE
        pattern = r'<span>Site</span>([A-Z0-9\.]+)</span>'
        matches = re.findall(pattern, content)
        
        # Remove duplicates and sort
        actual_locations = sorted(list(set(matches)))
        return actual_locations
    except FileNotFoundError:
        print("❌ Hydrophone.html not found. Run Hydrophone.py first to generate the dashboard.")
        return []
    except Exception as e:
        print(f"❌ Error reading HTML file: {e}")
        return []

def analyze_divert_emails():
    """Analyze recent divert emails to find location names."""
    try:
        from gmail_divert_parser import GmailDivertParser
        
        parser = GmailDivertParser()
        if not parser.authenticate():
            print("❌ Could not authenticate with Gmail")
            return {}
        
        # Get recent emails
        print("📧 Analyzing recent divert emails...")
        parser.update_divert_status(days_back=30)
        
        # Extract unique email location names from history
        email_locations = set()
        for event in parser.divert_history:
            # Get original email subject and body to extract raw location names
            subject = event.get('email_subject', '')
            if '[Divert]' in subject:
                # Re-parse the email to get original location names
                messages = parser.search_divert_emails(days_back=30)
                for message in messages[:10]:  # Check first 10 for speed
                    email_subject, email_body, email_date = parser.get_email_content(message['id'])
                    if subject in email_subject:
                        parsed = parser.parse_divert_email(email_subject, email_body, email_date)
                        for location in parsed['locations'].keys():
                            email_locations.add(location)
                        break
        
        return email_locations
    except ImportError:
        print("❌ Gmail parser not available")
        return set()
    except Exception as e:
        print(f"❌ Error analyzing emails: {e}")
        return set()

def get_current_mappings():
    """Get current location mappings from the parser."""
    try:
        from gmail_divert_parser import LOCATION_MAPPING
        return LOCATION_MAPPING
    except ImportError:
        return {}

def main():
    print("🗺️  Location Mapping Setup Tool")
    print("=" * 50)
    
    # Get actual hydrophone locations
    print("\n📍 Extracting actual hydrophone locations from dashboard...")
    actual_locations = extract_hydrophone_locations()
    
    if actual_locations:
        print(f"✅ Found {len(actual_locations)} active hydrophone locations:")
        for i, location in enumerate(actual_locations, 1):
            print(f"   {i:2d}. {location}")
    else:
        print("❌ No locations found. Please run Hydrophone.py first.")
        return 1
    
    # Get email locations
    print(f"\n📧 Analyzing divert email locations...")
    email_locations = analyze_divert_emails()
    
    if email_locations:
        print(f"✅ Found {len(email_locations)} unique email locations:")
        for i, location in enumerate(sorted(email_locations), 1):
            print(f"   {i:2d}. '{location}'")
    else:
        print("❌ No email locations found.")
    
    # Get current mappings
    print(f"\n🗺️  Current location mappings:")
    current_mappings = get_current_mappings()
    
    if current_mappings:
        for email_loc, hydro_locs in current_mappings.items():
            print(f"   '{email_loc}' → {hydro_locs}")
    else:
        print("❌ No current mappings found.")
    
    # Analysis
    print(f"\n🔍 MAPPING ANALYSIS")
    print("=" * 30)
    
    # Check for unmapped email locations
    unmapped_email_locations = []
    mapped_to_nonexistent = []
    
    for email_loc in email_locations:
        if email_loc not in current_mappings:
            unmapped_email_locations.append(email_loc)
        else:
            # Check if mapped hydrophone locations actually exist
            mapped_hydros = current_mappings[email_loc]
            for hydro_loc in mapped_hydros:
                if hydro_loc not in actual_locations:
                    mapped_to_nonexistent.append((email_loc, hydro_loc))
    
    if unmapped_email_locations:
        print(f"\n⚠️  Email locations without mappings:")
        for loc in unmapped_email_locations:
            print(f"   - '{loc}'")
    
    if mapped_to_nonexistent:
        print(f"\n❌ Mappings to non-existent hydrophone locations:")
        for email_loc, hydro_loc in mapped_to_nonexistent:
            print(f"   - '{email_loc}' → '{hydro_loc}' ('{hydro_loc}' not found in active hydrophones)")
    
    # Suggest corrections
    print(f"\n💡 SUGGESTED CORRECTIONS")
    print("=" * 30)
    
    # Look for potential matches based on similar names
    suggestions = []
    
    for email_loc in unmapped_email_locations:
        # Simple fuzzy matching
        email_clean = email_loc.replace('[', '').replace(']', '').replace(' ', '').upper()
        for hydro_loc in actual_locations:
            hydro_clean = hydro_loc.replace('.', '').upper()
            # Check for partial matches
            if email_clean in hydro_clean or hydro_clean in email_clean:
                suggestions.append((email_loc, hydro_loc))
    
    # Known common mappings from email patterns
    known_patterns = {
        'Barkley Cnyn': ['BACUS'],  # Barkley Canyon → Barkley Canyon Underwater Seismograph
        'ODP 1027': ['ODP1027'],   # If this location exists
        'Endeavour': ['ENDEAVOUR'], # If this location exists
        'ODP 889': ['ODP889'],     # If this location exists  
        'Folger Pass': ['FOLGERPASS'], # If this location exists
        'SoG_Central': ['DIIP', 'CBYIP', 'HBIP', 'HRBIP', 'KVIP'],  # Might be one of these VIP locations
    }
    
    print("Potential mapping suggestions:")
    for email_loc, hydro_loc in suggestions:
        print(f"   '{email_loc}' → '{hydro_loc}' (name similarity)")
    
    # Check known patterns against actual locations
    print(f"\nValidating known patterns against actual locations:")
    for email_loc, suggested_hydros in known_patterns.items():
        if email_loc in email_locations:
            existing_hydros = [h for h in suggested_hydros if h in actual_locations]
            if existing_hydros:
                print(f"   ✅ '{email_loc}' → {existing_hydros}")
            else:
                print(f"   ❌ '{email_loc}' → {suggested_hydros} (none exist)")
    
    # Generate updated mapping code
    print(f"\n📝 UPDATED MAPPING CODE")
    print("=" * 30)
    print("# Copy this into gmail_divert_parser.py LOCATION_MAPPING:")
    print("LOCATION_MAPPING = {")
    
    # Include existing working mappings
    for email_loc, hydro_locs in current_mappings.items():
        # Only include if all mapped locations exist
        valid_hydros = [h for h in hydro_locs if h in actual_locations]
        if valid_hydros and email_loc in email_locations:
            print(f"    '{email_loc}': {valid_hydros},")
    
    # Add suggestions for unmapped locations
    for email_loc in unmapped_email_locations:
        print(f"    # TODO: Map '{email_loc}' to appropriate hydrophone location(s)")
        # Show potential matches
        potential = [hydro for email_test, hydro in suggestions if email_test == email_loc]
        if potential:
            print(f"    # Suggestions: {potential}")
        print(f"    '{email_loc}': [],  # UPDATE THIS")
    
    print("}")
    
    print(f"\n✅ Analysis complete! Review the suggestions above and update gmail_divert_parser.py")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 