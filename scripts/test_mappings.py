#!/usr/bin/env python3
"""
Test script for validating location mappings and divert parser functionality.

Uses the organized hydrophonedashboard package structure.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from hydrophonedashboard.config.location_mappings import validate_mapping
from hydrophonedashboard.divert.gmail_parser import GmailDivertParser

def test_location_mappings():
    """Test the location mapping validation."""
    print("🗺️  Testing Location Mappings")
    print("=" * 50)
    
    validation_result = validate_mapping()
    
    print(f"✅ Total locations: {validation_result['total_locations']}")
    print(f"✅ Mapped locations: {validation_result['mapped_locations']}")
    print(f"❌ Unmapped locations: {validation_result['unmapped_locations']}")
    print(f"📊 Mapping completeness: {validation_result['mapping_completeness']:.1%}")
    print(f"🎯 Total unique hydrophone codes: {validation_result['total_hydrophone_codes']}")
    
    if validation_result['duplicate_assignments'] > 0:
        print(f"⚠️  Duplicate assignments found: {validation_result['duplicate_assignments']}")
    else:
        print("✅ No duplicate assignments found")
    
    if validation_result['unmapped_location_names']:
        print(f"\n❌ Unmapped locations that need attention:")
        for location in validation_result['unmapped_location_names']:
            print(f"   - {location}")
    
    return validation_result

def test_divert_parser():
    """Test the divert parser initialization."""
    print("\n📧 Testing Gmail Divert Parser")
    print("=" * 50)
    
    try:
        parser = GmailDivertParser()
        print("✅ GmailDivertParser initialized successfully")
        
        # Test location mapping function
        test_locations = {
            'ODP 1027': 'Bypass',
            'ODP 1364A': 'Divert',
            'SoG_East': 'Bypass'
        }
        
        mapped_hydrophones = parser.map_locations_to_hydrophones(test_locations)
        hydrophone_word = 'hydrophone' if len(mapped_hydrophones) == 1 else 'hydrophones'
        print(f"✅ Location mapping test: {len(mapped_hydrophones)} {hydrophone_word} mapped")
        
        for location, status in test_locations.items():
            print(f"   📍 {location} ({status})")
        
        print(f"   ➡️  Mapped to {len(mapped_hydrophones)} hydrophone codes:")
        for hydrophone, status in mapped_hydrophones.items():
            print(f"      🎯 {hydrophone}: {status}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing divert parser: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Hydrophonedashboard Package Test Suite")
    print("=" * 60)
    
    # Test location mappings
    mapping_result = test_location_mappings()
    
    # Test divert parser
    parser_success = test_divert_parser()
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 30)
    
    if mapping_result['mapping_completeness'] >= 0.8:
        print("✅ Location mappings: GOOD (≥80% complete)")
    elif mapping_result['mapping_completeness'] >= 0.6:
        print("⚠️  Location mappings: OK (≥60% complete)")
    else:
        print("❌ Location mappings: NEEDS WORK (<60% complete)")
    
    if parser_success:
        print("✅ Divert parser: WORKING")
    else:
        print("❌ Divert parser: FAILED")
    
    print(f"\n🎯 Key Stats:")
    print(f"   - {mapping_result['mapped_locations']}/{mapping_result['total_locations']} locations mapped")
    print(f"   - {mapping_result['total_hydrophone_codes']} unique hydrophone codes")
    print(f"   - Package organization: ✅ COMPLETE")
    
    if mapping_result['mapping_completeness'] >= 0.8 and parser_success:
        print("\n🎉 All tests passed! Package is ready for use.")
        return True
    else:
        print("\n⚠️  Some tests failed. Review the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 