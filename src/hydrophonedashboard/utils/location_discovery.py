#!/usr/bin/env python3
"""
Hydrophone Location Discovery
Lists all locations with hydrophone data using the same approach as the 
hydrophonedatarequests GitHub repo discovery interface.
"""

import os
import re
from datetime import datetime, timedelta
from onc.onc import ONC
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()

def extract_name_from_citation(citation_string):
    """Extract a location name from the citation string, avoiding generic terms."""
    if not citation_string:
        return None

    # Try to find patterns like "... YYYY. [Location Name] Hydrophone Deployed YYYY-MM-DD..."
    match = re.search(r'\.\s*\d{4}\.\s*(.*?)(?:\s+Hydrophone)?\s+Deployed\s+\d{4}-\d{2}-\d{2}', citation_string, re.IGNORECASE)

    if match:
        potential_name = match.group(1).strip()
        # Avoid overly generic terms
        if potential_name and potential_name.lower() not in ["hydrophone", "underwater network"]:
            potential_name = potential_name.rstrip('.,;:!?)(')
            return potential_name

    # Fallback: Simpler pattern if the above fails
    match_simple = re.search(r'\.\s*\d{4}\.\s*(.*)', citation_string)
    if match_simple:
        potential_name = match_simple.group(1).strip()
        
        # Remove trailing date/doi parts
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', potential_name)
        if date_match:
            potential_name = potential_name[:date_match.start()].strip()
        
        doi_match = re.search(r'https?://doi.org', potential_name, re.IGNORECASE)
        if doi_match:
            potential_name = potential_name[:doi_match.start()].strip()

        # Remove trailing hydrophone/deployment info
        potential_name = re.sub(r'\s+Hydrophone\s+Deployed.*$', '', potential_name, flags=re.IGNORECASE).strip()
        potential_name = re.sub(r'\s+Deployed.*$', '', potential_name, flags=re.IGNORECASE).strip()
        potential_name = potential_name.rstrip('.,;:!?)(')

        if potential_name and potential_name.lower() not in ["hydrophone", "underwater network"]:
            return potential_name

    return None

def list_hydrophone_locations():
    """
    List all locations with hydrophone data using the same approach as the GitHub repo
    """
    print("Hydrophone Location Discovery")
    print("=" * 50)
    
    # Get ONC token
    token = os.getenv('ONC_TOKEN')
    if not token:
        print("❌ ONC_TOKEN not found in environment variables")
        return
    
    onc = ONC(token)
    
    try:
        print("🔍 Getting all hydrophone devices...")
        
        # Step 1: Get location map first (needed for display names)
        print("   Getting location map...")
        loc_response = onc.getLocations({})
        loc_map = {loc.get('locationCode'): loc.get('locationName', '') 
                   for loc in loc_response if isinstance(loc, dict)}
        print(f"   Found {len(loc_map)} locations in map")
        
        # Step 2: Get all hydrophones (this is the key difference from the original approach)
        print("   Getting all hydrophone devices...")
        all_hydrophones = onc.getDevices({"deviceCategoryCode": "HYDROPHONE"})
        if not isinstance(all_hydrophones, list):
            print("❌ Unexpected response format from getDevices")
            return
        
        if not all_hydrophones:
            print("❌ No hydrophone devices found")
            return
        
        # Step 4: Print what we found
        device_word = 'device' if len(all_hydrophones) == 1 else 'devices'
        print(f"   Found {len(all_hydrophones)} hydrophone {device_word}")
        
        # Step 3: Get deployments for all hydrophones
        print("   Getting deployments for all devices...")
        all_deployments = []
        
        # Use a broad date range to capture all historical deployments
        date_from = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        date_to = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        for device in all_hydrophones:
            device_code = device.get('deviceCode')
            if not device_code:
                continue
                
            try:
                deployments = onc.getDeployments({
                    'deviceCode': device_code,
                    'dateFrom': date_from,
                    'dateTo': date_to
                })
                all_deployments.extend(deployments)
            except Exception as e:
                print(f"   Warning: Could not get deployments for {device_code}: {e}")
                continue
        
        print(f"   Found {len(all_deployments)} total deployments")
        
        # Step 4: Group deployments by PARENT location code (like the GitHub repo does)
        by_parent_loc = defaultdict(list)
        parent_codes_found = set()

        for deployment in all_deployments:
            loc_code_from_dep = deployment.get('locationCode')
            if not loc_code_from_dep:
                continue

            # Split on '.' to get parent location
            parent_code = loc_code_from_dep
            if '.' in loc_code_from_dep:
                parent_code = loc_code_from_dep.split('.')[0]

            by_parent_loc[parent_code].append(deployment)
            parent_codes_found.add(parent_code)
        
        if not by_parent_loc:
            print("❌ No deployments found with processable location codes")
            return

        sorted_parent_codes = sorted(list(parent_codes_found))
        
        # Step 5: Build parent location choices with device codes (like the GitHub repo)
        parent_loc_choices = []
        
        # Define known generic/undesirable names from loc_map (from the GitHub repo)
        GENERIC_LOC_MAP_NAMES = {"Hydrophone Array - Box Type", "Underwater Network"}
        
        print("   Processing parent locations and hydrophones...")
        for parent_code in sorted_parent_codes:
            display_name = None
            deployments_at_parent = by_parent_loc[parent_code]
            first_deployment = deployments_at_parent[0] if deployments_at_parent else None

            # Naming logic (matching the GitHub repo approach)
            # 1. Try to get name from loc_map, but check if it's generic
            parent_map_name = loc_map.get(parent_code)
            is_generic_from_map = False
            if parent_map_name:
                if parent_map_name in GENERIC_LOC_MAP_NAMES:
                    is_generic_from_map = True
                else:
                    # Use the map name if it exists and is NOT generic
                    display_name = parent_map_name

            # 2. Try citation parsing if map lookup failed or gave a generic name
            if display_name is None:
                if first_deployment:
                    citation_text = first_deployment.get('citation', {}).get('citation') if isinstance(first_deployment.get('citation'), dict) else None
                    citation_name = extract_name_from_citation(citation_text)
                    if citation_name:
                        display_name = citation_name

            # 3. Fallback: Use generic map name or code itself
            if display_name is None:
                if parent_map_name and is_generic_from_map:
                    display_name = parent_map_name
                else:
                    display_name = parent_code

            # Get device list (codes only)
            device_codes_only = set()
            for dep in deployments_at_parent:
                device_code = dep.get('deviceCode')
                if device_code:
                    device_codes_only.add(device_code)

            device_count = len(device_codes_only)
            
            # Store for final display
            parent_loc_choices.append({
                'locationCode': parent_code,
                'locationName': display_name,
                'deviceCount': device_count
            })
        
        # Step 6: Sort and display results in GitHub repo format
        sorted_locations = sorted(parent_loc_choices, key=lambda x: x['locationCode'])
        
        print(f"\n2a. Select Location:")
        print("=" * 80)
        
        for loc in sorted_locations:
            print(f"{loc['locationName']} [{loc['locationCode']}] (Devs: {loc['deviceCount']})")
                
        print(f"\n✅ Discovery complete! Found {len(sorted_locations)} locations with hydrophone data")
        
        # Also show any ODP sites found
        odp_sites = [loc for loc in sorted_locations if 'ODP' in loc['locationName'].upper()]
        if odp_sites:
            print(f"\n🎯 ODP Sites found:")
            for odp in odp_sites:
                print(f"   {odp['locationName']} [{odp['locationCode']}]")
        
        return sorted_locations
        
    except Exception as e:
        print(f"❌ Error fetching location data: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    list_hydrophone_locations() 