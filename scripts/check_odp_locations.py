#!/usr/bin/env python3
"""
ODP Location Checker
Queries the ONC API to get full location names and check if any correspond to ODP drilling sites.
"""

import os
import pandas as pd
from onc.onc import ONC
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_odp_locations():
    """Check if any hydrophone locations correspond to ODP drilling sites"""
    
    print("ODP Location Checker")
    print("=" * 50)
    
    # Get ONC token
    token = os.getenv('ONC_TOKEN')
    if not token:
        print("❌ ONC_TOKEN not found in environment variables")
        return
    
    onc = ONC(token)
    
    # Get current hydrophone deployments
    print("🔍 Fetching current hydrophone deployments...")
    datefrom = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    try:
        result = onc.getDeployments({'deviceCategoryCode': 'HYDROPHONE', 'dateFrom': datefrom})
        print(f"   Found {len(result)} deployments")
        
        locations_info = []
        
        for deployment in result:
            if not deployment.get('end'):  # Only active deployments
                location_code = deployment['locationCode']
                
                # Get detailed location information
                try:
                    location_details = onc.getLocations({'locationCode': location_code})
                    if location_details:
                        location_info = {
                            'locationCode': location_code,
                            'locationName': location_details[0].get('locationName', 'Unknown'),
                            'depth': deployment.get('depth', 'Unknown'),
                            'begin': deployment.get('begin', 'Unknown')
                        }
                        locations_info.append(location_info)
                        
                except Exception as e:
                    print(f"   Warning: Could not get details for {location_code}: {e}")
                    
        print(f"\n📍 Found {len(locations_info)} active hydrophone locations:")
        print("=" * 80)
        
        # Check for ODP references
        odp_candidates = []
        
        for loc in locations_info:
            location_name = loc['locationName'].upper()
            location_code = loc['locationCode']
            
            print(f"🌊 {location_code:12} | {loc['locationName']}")
            print(f"   📏 Depth: {loc['depth']} m | 📅 Since: {loc['begin'][:10] if loc['begin'] != 'Unknown' else 'Unknown'}")
            
            # Check for ODP references in location name
            if any(keyword in location_name for keyword in ['ODP', 'OCEAN DRILLING', 'DRILLING PROGRAM', 'SITE 1027', 'SITE 889']):
                odp_candidates.append({
                    'locationCode': location_code,
                    'locationName': loc['locationName'],
                    'potential_odp': True
                })
                print(f"   🎯 POTENTIAL ODP SITE! Contains drilling-related keywords")
                
            # Check for Cascadia Basin locations (where ODP sites are typically located)
            elif any(keyword in location_name for keyword in ['CASCADIA', 'BASIN', 'BARKLEY', 'FOLGER']):
                odp_candidates.append({
                    'locationCode': location_code,
                    'locationName': loc['locationName'],
                    'potential_odp': False,
                    'note': 'In Cascadia Basin region where ODP sites are located'
                })
                print(f"   📍 In Cascadia Basin region (where ODP sites are typically located)")
                
            print()
        
        # Summary of ODP analysis
        print("\n" + "=" * 80)
        print("🔬 ODP SITE ANALYSIS SUMMARY")
        print("=" * 80)
        
        if odp_candidates:
            print(f"Found {len(odp_candidates)} locations that might correspond to ODP sites:")
            print()
            
            for candidate in odp_candidates:
                print(f"📍 {candidate['locationCode']}: {candidate['locationName']}")
                if candidate.get('potential_odp'):
                    print(f"   🎯 HIGH PROBABILITY - Contains ODP/drilling keywords")
                else:
                    print(f"   📍 POSSIBLE - {candidate.get('note', 'In relevant geographic region')}")
                print()
                
        else:
            print("❌ No obvious ODP site references found in location names")
            print("   The ODP 1027 and ODP 889 from divert emails may refer to:")
            print("   • Historic drilling sites no longer monitored")
            print("   • Sites with different ONC location codes")
            print("   • Sites that were decommissioned")
            
        print("\n💡 RECOMMENDATIONS:")
        print("   1. ODP 1027 and ODP 889 likely refer to historic Ocean Drilling Program sites")
        print("   2. These may not have active hydrophone deployments anymore")
        print("   3. Consider leaving these mappings empty ([]) in the divert parser")
        print("   4. Contact ONC if you need historical information about these sites")
        
    except Exception as e:
        print(f"❌ Error fetching deployment data: {e}")
        
if __name__ == "__main__":
    check_odp_locations() 