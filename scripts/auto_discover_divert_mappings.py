#!/usr/bin/env python3
"""
Automatic Divert Location Mapping Generator
Uses the ONC API to discover all hydrophone locations and automatically 
generate mappings between divert email location names and actual hydrophone codes.
"""

import os
import re
import json
from collections import defaultdict
from datetime import datetime, timedelta
from onc.onc import ONC
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def discover_hydrophone_locations():
    """
    Discover all current hydrophone locations using the ONC API
    Returns a dict with location details including full names
    """
    print("🔍 Discovering hydrophone locations via ONC API...")
    
    # Get ONC token
    token = os.getenv('ONC_TOKEN')
    if not token:
        raise ValueError("ONC_TOKEN not found in environment variables")
    
    onc = ONC(token)
    
    # Get current hydrophone deployments
    datefrom = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    try:
        deployments = onc.getDeployments({
            'deviceCategoryCode': 'HYDROPHONE', 
            'dateFrom': datefrom
        })
        
        locations_info = {}
        
        print(f"   Found {len(deployments)} hydrophone deployments")
        
        for deployment in deployments:
            if not deployment.get('end'):  # Only active deployments
                location_code = deployment['locationCode']
                
                # Get detailed location information
                try:
                    location_details = onc.getLocations({'locationCode': location_code})
                    if location_details:
                        location_info = location_details[0]
                        
                        # Store comprehensive location data
                        locations_info[location_code] = {
                            'locationCode': location_code,
                            'locationName': location_info.get('locationName', 'Unknown'),
                            'depth': deployment.get('depth', 'Unknown'),
                            'begin': deployment.get('begin', 'Unknown'),
                            'deviceCode': deployment.get('deviceCode', 'Unknown'),
                            'dataSearchURL': location_info.get('dataSearchURL', ''),
                            # Additional fields that might help with mapping
                            'lat': location_info.get('lat'),
                            'lon': location_info.get('lon'),
                            'description': location_info.get('description', ''),
                        }
                        
                except Exception as e:
                    print(f"   Warning: Could not get details for {location_code}: {e}")
                    
        print(f"   Successfully mapped {len(locations_info)} active hydrophone locations")
        return locations_info
        
    except Exception as e:
        print(f"❌ Error fetching deployment data: {e}")
        return {}

def analyze_location_names(locations_info):
    """
    Analyze location names to identify potential divert mapping patterns
    """
    print("\n📊 Analyzing location names for divert mapping patterns...")
    
    # Categorize locations by potential divert systems
    sog_locations = []      # Strait of Georgia DDS
    saanich_locations = []  # Saanich DDS  
    nc_dds_locations = []   # NC-DDS
    odp_locations = []      # Ocean Drilling Program sites
    other_locations = []    # Uncategorized
    
    for loc_code, info in locations_info.items():
        name = info['locationName'].upper()
        
        print(f"   🌊 {loc_code:12} | {info['locationName']}")
        
        # Check for Strait of Georgia locations
        if any(keyword in name for keyword in ['STRAIT OF GEORGIA', 'SOG', 'GEORGIA STRAIT']):
            sog_locations.append((loc_code, info))
            print(f"      → Identified as SoG DDS location")
            
        # Check for Saanich locations  
        elif any(keyword in name for keyword in ['SAANICH', 'PATRICIA BAY']):
            saanich_locations.append((loc_code, info))
            print(f"      → Identified as Saanich DDS location")
            
        # Check for ODP sites (Ocean Drilling Program)
        elif any(keyword in name for keyword in ['ODP', 'OCEAN DRILLING', 'DRILLING PROGRAM']):
            odp_locations.append((loc_code, info))
            print(f"      → 🎯 IDENTIFIED ODP SITE!")
            
        # Check for known Cascadia/NC-DDS regions
        elif any(keyword in name for keyword in ['BARKLEY', 'CASCADIA', 'ENDEAVOUR', 'FOLGER']):
            nc_dds_locations.append((loc_code, info))
            print(f"      → Identified as NC-DDS location")
            
        else:
            other_locations.append((loc_code, info))
            print(f"      → Uncategorized location")
    
    return {
        'sog_locations': sog_locations,
        'saanich_locations': saanich_locations, 
        'nc_dds_locations': nc_dds_locations,
        'odp_locations': odp_locations,
        'other_locations': other_locations
    }

def extract_location_mapping_clues(locations_info):
    """
    Extract clues from location names that might match divert email patterns
    """
    print("\n🔍 Extracting location mapping clues...")
    
    mapping_clues = {}
    
    for loc_code, info in locations_info.items():
        name = info['locationName']
        
        # Look for patterns like "ODP 1027C [CBCH]" or "Barkley Canyon [BACNH]"
        bracket_match = re.search(r'\[([A-Z0-9\.]+)\]', name)
        if bracket_match:
            contained_code = bracket_match.group(1)
            print(f"   📍 {name}")
            print(f"      Contains location code: {contained_code}")
            if contained_code != loc_code:
                print(f"      Maps {contained_code} → {loc_code}")
                mapping_clues[contained_code] = loc_code
        
        # Look for ODP site numbers
        odp_match = re.search(r'ODP\s*(\d+)[A-Z]?', name, re.IGNORECASE)
        if odp_match:
            odp_number = odp_match.group(1)
            print(f"   🎯 ODP Site {odp_number} found: {name} → {loc_code}")
            mapping_clues[f'ODP {odp_number}'] = loc_code
            mapping_clues[f'ODP {odp_number}C'] = loc_code  # Common variant
            
        # Look for geographic name patterns that might match divert emails
        geographic_patterns = {
            'Barkley Canyon': ['BARKLEY', 'CANYON'],
            'Cascadia Basin': ['CASCADIA', 'BASIN'], 
            'Endeavour': ['ENDEAVOUR'],
            'Folger': ['FOLGER'],
            'Saanich': ['SAANICH'],
        }
        
        for pattern_name, keywords in geographic_patterns.items():
            if all(keyword in name.upper() for keyword in keywords):
                print(f"   📍 Geographic match: {pattern_name} → {loc_code}")
                mapping_clues[pattern_name] = loc_code
    
    return mapping_clues

def generate_divert_mapping(locations_info, mapping_clues, categorized_locations):
    """
    Generate the Python code for the divert location mapping
    """
    print("\n🔧 Generating divert location mapping...")
    
    # Group locations by arrays (H1, H2, H3, H4)
    location_arrays = defaultdict(list)
    
    for loc_code in locations_info.keys():
        # Extract base location (remove .H1, .H2, etc.)
        base_match = re.match(r'([A-Z]+)(?:\.H\d+)?$', loc_code)
        if base_match:
            base_location = base_match.group(1)
            location_arrays[base_location].append(loc_code)
    
    # Sort arrays naturally
    for base_location in location_arrays:
        location_arrays[base_location].sort()
    
    mapping_code = '''# Location mapping - maps email location names to hydrophone location codes
# Auto-generated from ONC API discovery
LOCATION_MAPPING = {
    # SoG DDS system locations'''
    
    # Add SoG locations
    sog_mappings = []
    for loc_code, info in categorized_locations['sog_locations']:
        base_match = re.match(r'([A-Z]+)', loc_code)
        if base_match:
            base = base_match.group(1)
            if location_arrays[base]:
                if 'ECHO' in base:
                    sog_mappings.append(f"    'SoG_East': {location_arrays[base]},  # {info['locationName']}")
                elif 'CBCH' in base or 'CASCADIA' in info['locationName'].upper():
                    sog_mappings.append(f"    'SoG_Delta': {location_arrays[base]},  # {info['locationName']}")
                elif 'PSGCH' in base or 'CENTRAL' in info['locationName'].upper():
                    sog_mappings.append(f"    'SoG_Central': {location_arrays[base]},  # {info['locationName']}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_sog = []
    for mapping in sog_mappings:
        if mapping not in seen:
            unique_sog.append(mapping)
            seen.add(mapping)
    
    mapping_code += '\n' + '\n'.join(unique_sog)
    
    # Add Saanich locations
    mapping_code += '\n    \n    # Saanich DDS system locations'
    for loc_code, info in categorized_locations['saanich_locations']:
        base_match = re.match(r'([A-Z]+)', loc_code)
        if base_match:
            base = base_match.group(1)
            if location_arrays[base]:
                mapping_code += f"\n    'Saanich_Inlet': {location_arrays[base]},  # {info['locationName']}"
                break  # Only add once
    
    # Add NC-DDS locations with bracket format
    mapping_code += '\n    \n    # NC-DDS system locations - with bracket format'
    
    nc_mappings = {
        1: ('Barkley Cnyn', 'BACNH', 'BACUS'),
        2: ('ODP 1027', 'CBCH'),
        3: ('Endeavour', 'KEMFH'), 
        4: ('ODP 889', None),  # To be identified
        5: ('Folger Pass', 'FGPD'),
    }
    
    for num, (name, *base_codes) in nc_mappings.items():
        hydrophones = []
        for base_code in base_codes:
            if base_code and base_code in location_arrays:
                hydrophones.extend(location_arrays[base_code])
        
        # Special handling for ODP sites found in discovery
        if 'ODP' in name:
            for loc_code, info in categorized_locations['odp_locations']:
                location_name = info['locationName']
                if '1027' in location_name and '1027' in name:
                    # Found ODP 1027 site
                    base_match = re.match(r'([A-Z]+)', loc_code)
                    if base_match:
                        base = base_match.group(1)
                        if location_arrays[base]:
                            hydrophones = location_arrays[base]
                    comment = f"  # {location_name}"
                elif '889' in location_name and '889' in name:
                    # Found ODP 889 site  
                    base_match = re.match(r'([A-Z]+)', loc_code)
                    if base_match:
                        base = base_match.group(1)
                        if location_arrays[base]:
                            hydrophones = location_arrays[base]
                    comment = f"  # {location_name}"
                else:
                    comment = f"  # Need to identify corresponding ONC location"
            else:
                comment = f"  # Need to identify corresponding ONC location"
        else:
            # Get comment from first matching location
            comment = ""
            for base_code in base_codes:
                if base_code and base_code in location_arrays:
                    for loc_code, info in locations_info.items():
                        if loc_code.startswith(base_code):
                            comment = f"  # {info['locationName']}"
                            break
                    break
        
        mapping_code += f"\n    '[{num}] {name}': {hydrophones},{comment}"
    
    # Add fallback format without brackets
    mapping_code += '\n    \n    # NC-DDS system locations - without bracket format (fallback)'
    for num, (name, *base_codes) in nc_mappings.items():
        hydrophones = []
        for base_code in base_codes:
            if base_code and base_code in location_arrays:
                hydrophones.extend(location_arrays[base_code])
        
        comment = ""
        for base_code in base_codes:
            if base_code and base_code in location_arrays:
                for loc_code, info in locations_info.items():
                    if loc_code.startswith(base_code):
                        comment = f"  # {info['locationName']}"
                        break
                break
        
        mapping_code += f"\n    '{name}': {hydrophones},{comment}"
    
    mapping_code += '\n}'
    
    return mapping_code

def main():
    """Main function to discover and generate divert mappings"""
    print("=" * 80)
    print("🚀 AUTOMATIC DIVERT LOCATION MAPPING GENERATOR")  
    print("=" * 80)
    
    try:
        # Step 1: Discover all hydrophone locations
        locations_info = discover_hydrophone_locations()
        if not locations_info:
            print("❌ No locations discovered. Exiting.")
            return
            
        # Step 2: Analyze and categorize locations
        categorized = analyze_location_names(locations_info)
        
        # Step 3: Extract mapping clues
        mapping_clues = extract_location_mapping_clues(locations_info)
        
        # Step 4: Generate the mapping code
        mapping_code = generate_divert_mapping(locations_info, mapping_clues, categorized)
        
        # Step 5: Display results
        print("\n" + "=" * 80)
        print("✨ GENERATED DIVERT LOCATION MAPPING")
        print("=" * 80)
        print(mapping_code)
        
        # Step 6: Save to file
        output_file = 'auto_generated_divert_mapping.py'
        with open(output_file, 'w') as f:
            f.write(f'"""\nAuto-generated divert location mapping\nGenerated on: {datetime.now()}\n"""\n\n')
            f.write(mapping_code)
            
        print(f"\n💾 Mapping saved to: {output_file}")
        
        # Step 7: Summary
        print(f"\n📊 DISCOVERY SUMMARY:")
        print(f"   Total hydrophone locations: {len(locations_info)}")
        print(f"   SoG DDS locations: {len(categorized['sog_locations'])}")
        print(f"   Saanich DDS locations: {len(categorized['saanich_locations'])}")
        print(f"   NC-DDS locations: {len(categorized['nc_dds_locations'])}")
        print(f"   ODP sites found: {len(categorized['odp_locations'])}")
        print(f"   Other locations: {len(categorized['other_locations'])}")
        
        if categorized['odp_locations']:
            print(f"\n🎯 ODP SITES DISCOVERED:")
            for loc_code, info in categorized['odp_locations']:
                print(f"   {loc_code}: {info['locationName']}")
        
        print(f"\n✅ Ready to update gmail_divert_parser.py with the generated mapping!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 