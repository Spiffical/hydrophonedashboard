"""
Location Mappings for Hydrophone Divert Monitoring

Maps email location names from divert notifications to actual ONC hydrophone location codes.
Based on actual ONC hydrophone deployments and divert system naming conventions.

System Overview:
- SoG DDS: Strait of Georgia Dynamic Data System  
- NC-DDS: Northern Canadian Dynamic Data System
- Saanich DDS: Saanich Inlet Dynamic Data System

Location Discovery Sources:
- Manual analysis of divert emails
- ONC API location discovery (list_hydrophone_locations.py)  
- Cross-reference with ONC data portal
"""

# Location mapping - maps email location names to hydrophone location codes
# Based on actual ONC hydrophone deployments and divert system naming
LOCATION_MAPPING = {
    # ================================
    # SoG DDS (Strait of Georgia) System Locations
    # ================================
    'SoG_East': ['ECHO3.H1', 'ECHO3.H2', 'ECHO3.H3', 'ECHO3.H4'],  # SoG East = ECHO3 array
    'SoG_Delta': ['CBCH.H1', 'CBCH.H2', 'CBCH.H3', 'CBCH.H4'],    # SoG Delta = Cascadia Basin array
    'SoG_Central': ['PSGCH.H1', 'PSGCH.H3'],  # SoG Central = PSGCH array (only H1 and H3 active)
    
    # ================================
    # Saanich DDS System Locations  
    # ================================
    'Saanich_Inlet': ['PVIPH.H1', 'PVIPH.H3'],  # Saanich Inlet = PVIPH array (only H1 and H3 active)
    
    # ================================
    # NC-DDS (Northern Canadian) System Locations - with bracket format
    # ================================
    '[1] Barkley Cnyn': ['BACNH.H1', 'BACNH.H2', 'BACNH.H3', 'BACNH.H4', 'BACUS'],  # Barkley Canyon (main array + upper slope)
    '[2] ODP 1027': ['CBCH.H1', 'CBCH.H2', 'CBCH.H3', 'CBCH.H4'],   # ODP 1027C = Cascadia Basin (CBCH)
    '[3] Endeavour': ['KEMFH.H1', 'KEMFH.H2', 'KEMFH.H3', 'KEMFH.H4'],  # Endeavour = KEMFH array
    '[4] ODP 889': [],    # ODP 889 - need to identify corresponding ONC location code  
    '[5] Folger Pass': ['FGPD'],  # Folger Pass = Folger Deep
    
    # ================================
    # Additional ODP Sites (Ocean Drilling Program)
    # ================================
    'ODP 1364A': ['CQSH.H1', 'CQSH.H2', 'CQSH.H3', 'CQSH.H4'],  # ODP 1364A = Clayoquot Slope (CQSH)
    'ODP 1026': ['NC27.H3', 'NC27.H4'],  # ODP 1026 = NC27 array (only H3 and H4 active)
    
    # ================================
    # NC-DDS System Locations - without bracket format (fallback)
    # ================================
    'Barkley Cnyn': ['BACNH.H1', 'BACNH.H2', 'BACNH.H3', 'BACNH.H4', 'BACUS'],  # Barkley Canyon (main array + upper slope)
    'ODP 1027': ['CBCH.H1', 'CBCH.H2', 'CBCH.H3', 'CBCH.H4'],   # ODP 1027C = Cascadia Basin (CBCH)
    'Endeavour': ['KEMFH.H1', 'KEMFH.H2', 'KEMFH.H3', 'KEMFH.H4'],  # Endeavour = KEMFH array
    'ODP 889': [],    # ODP 889 - need to identify corresponding ONC location code
    'Folger Pass': ['FGPD'],  # Folger Pass = Folger Deep
    
    # ================================
    # Additional Location Mappings (if these locations appear in emails)
    # ================================
    'Burrard Inlet': ['BIIP'],  # Burrard Inlet
    'Cambridge Bay': ['CBYIP'],  # Cambridge Bay 
    'China Creek': ['CCIP'],   # China Creek
    'Clayoquot Slope': ['CQSH.H1', 'CQSH.H2', 'CQSH.H3', 'CQSH.H4'],  # Clayoquot Slope array (ODP 1364A)
    'Digby Island': ['DIIP'],  # Digby Island
    'Hartley Bay': ['HBIP'],   # Hartley Bay
    'Holyrood Bay': ['HRBIP'],  # Holyrood Bay / Conception Bay
    'Kitamaat Village': ['KVIP'],  # Kitamaat Village
}

# ================================
# System Classifications
# ================================
SOG_DDS_LOCATIONS = {
    'SoG_East', 'SoG_Delta', 'SoG_Central'
}

SAANICH_DDS_LOCATIONS = {
    'Saanich_Inlet'
}

NC_DDS_LOCATIONS = {
    '[1] Barkley Cnyn', '[2] ODP 1027', '[3] Endeavour', '[4] ODP 889', '[5] Folger Pass',
    'Barkley Cnyn', 'ODP 1027', 'Endeavour', 'ODP 889', 'Folger Pass'
}

ODP_LOCATIONS = {
    'ODP 1027', 'ODP 1364A', 'ODP 1026', 'ODP 889',
    '[2] ODP 1027', '[4] ODP 889'
}

# ================================
# Helper Functions
# ================================

def get_system_for_location(location_name):
    """
    Determine which divert system a location belongs to.
    
    Args:
        location_name: Location name from email
        
    Returns:
        str: System name ('SoG DDS', 'NC-DDS', 'Saanich DDS', or 'Unknown')
    """
    if location_name in SOG_DDS_LOCATIONS:
        return 'SoG DDS'
    elif location_name in NC_DDS_LOCATIONS:
        return 'NC-DDS'
    elif location_name in SAANICH_DDS_LOCATIONS:
        return 'Saanich DDS'
    else:
        return 'Unknown'

def get_hydrophone_codes(location_name):
    """
    Get the hydrophone codes for a given location name.
    
    Args:
        location_name: Location name from email
        
    Returns:
        list: List of hydrophone codes, or empty list if not found
    """
    return LOCATION_MAPPING.get(location_name, [])

def is_odp_location(location_name):
    """
    Check if a location is an ODP (Ocean Drilling Program) site.
    
    Args:
        location_name: Location name from email
        
    Returns:
        bool: True if it's an ODP location
    """
    return location_name in ODP_LOCATIONS

def get_all_mapped_locations():
    """
    Get all location names that have hydrophone mappings.
    
    Returns:
        list: List of location names with non-empty mappings
    """
    return [location for location, codes in LOCATION_MAPPING.items() if codes]

def get_unmapped_locations():
    """
    Get all location names that don't have hydrophone mappings yet.
    
    Returns:
        list: List of location names with empty mappings
    """
    return [location for location, codes in LOCATION_MAPPING.items() if not codes]

def validate_mapping():
    """
    Validate the location mapping for completeness and consistency.
    
    Returns:
        dict: Validation results with statistics
    """
    total_locations = len(LOCATION_MAPPING)
    mapped_locations = len(get_all_mapped_locations())
    unmapped_locations = len(get_unmapped_locations())
    
    # Check for duplicate hydrophone codes
    all_codes = []
    for codes in LOCATION_MAPPING.values():
        all_codes.extend(codes)
    
    unique_codes = set(all_codes)
    duplicates = len(all_codes) - len(unique_codes)
    
    return {
        'total_locations': total_locations,
        'mapped_locations': mapped_locations,
        'unmapped_locations': unmapped_locations,
        'mapping_completeness': mapped_locations / total_locations if total_locations > 0 else 0,
        'total_hydrophone_codes': len(unique_codes),
        'duplicate_assignments': duplicates,
        'unmapped_location_names': get_unmapped_locations()
    }

if __name__ == "__main__":
    # Print validation information when run directly
    print("Hydrophone Location Mapping Validation")
    print("=" * 50)
    
    validation = validate_mapping()
    
    print(f"Total locations: {validation['total_locations']}")
    print(f"Mapped locations: {validation['mapped_locations']}")
    print(f"Unmapped locations: {validation['unmapped_locations']}")
    print(f"Mapping completeness: {validation['mapping_completeness']:.1%}")
    print(f"Total unique hydrophone codes: {validation['total_hydrophone_codes']}")
    
    if validation['duplicate_assignments'] > 0:
        print(f"⚠️  Duplicate assignments: {validation['duplicate_assignments']}")
    
    if validation['unmapped_location_names']:
        print(f"\n❌ Unmapped locations:")
        for location in validation['unmapped_location_names']:
            print(f"   - {location}")
    
    print(f"\n🎯 ODP Sites:")
    for location in ODP_LOCATIONS:
        codes = get_hydrophone_codes(location)
        status = "✅" if codes else "❌"
        print(f"   {status} {location}: {codes}") 