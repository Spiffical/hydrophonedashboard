"""
Auto-generated divert location mapping
Generated on: 2025-07-02 14:12:13.136785
"""

# Location mapping - maps email location names to hydrophone location codes
# Auto-generated from ONC API discovery
LOCATION_MAPPING = {
    # SoG DDS system locations

    
    # Saanich DDS system locations
    
    # NC-DDS system locations - with bracket format
    '[1] Barkley Cnyn': ['BACNH.H1', 'BACNH.H2', 'BACNH.H3', 'BACNH.H4', 'BACUS'],  # Hydrophone A
    '[2] ODP 1027': ['CBCH.H1', 'CBCH.H2', 'CBCH.H3', 'CBCH.H4'],  # Need to identify corresponding ONC location
    '[3] Endeavour': ['KEMFH.H1', 'KEMFH.H2', 'KEMFH.H3', 'KEMFH.H4'],  # Hydrophone A
    '[4] ODP 889': [],  # Need to identify corresponding ONC location
    '[5] Folger Pass': ['FGPD'],  # Folger Deep
    
    # NC-DDS system locations - without bracket format (fallback)
    'Barkley Cnyn': ['BACNH.H1', 'BACNH.H2', 'BACNH.H3', 'BACNH.H4', 'BACUS'],  # Hydrophone A
    'ODP 1027': ['CBCH.H1', 'CBCH.H2', 'CBCH.H3', 'CBCH.H4'],  # Hydrophone A
    'Endeavour': ['KEMFH.H1', 'KEMFH.H2', 'KEMFH.H3', 'KEMFH.H4'],  # Hydrophone A
    'ODP 889': [],
    'Folger Pass': ['FGPD'],  # Folger Deep
}