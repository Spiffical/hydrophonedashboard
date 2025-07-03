#!/usr/bin/env python3
"""
Standalone script for discovering hydrophone locations.

Uses the organized hydrophonedashboard package structure.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from hydrophonedashboard.utils.location_discovery import list_hydrophone_locations

if __name__ == "__main__":
    print("🌊 Hydrophone Location Discovery Script")
    print("Using organized hydrophonedashboard package")
    print("-" * 50)
    
    locations = list_hydrophone_locations()
    
    if locations:
        print(f"\n📋 Summary: Found {len(locations)} unique locations")
        print("Script completed successfully!")
    else:
        print("❌ No locations found or error occurred")
        sys.exit(1) 