# Hydrophone Dashboard - Project Structure

## 📁 Organization Overview

The project has been reorganized into a clean, modular structure for better maintainability and extensibility.

```
hydrophonedashboard/
├── src/                           # Source code
│   └── hydrophonedashboard/      # Main package
│       ├── __init__.py           # Package initialization
│       ├── config/               # Configuration modules
│       │   ├── __init__.py
│       │   └── location_mappings.py  # Location mappings (extracted!)
│       ├── divert/              # Divert monitoring modules
│       │   ├── __init__.py
│       │   └── gmail_parser.py   # Gmail API divert parser
│       └── utils/               # Utility modules
│           ├── __init__.py
│           └── location_discovery.py  # Location discovery tools
├── scripts/                     # Standalone scripts
│   ├── list_locations.py       # Location discovery script
│   └── test_mappings.py         # Validation and testing
├── docs/                        # Documentation
│   └── PROJECT_STRUCTURE.md    # This file
├── assets/                      # Static assets (CSS, JS, images)
├── requirements.txt             # Python dependencies
├── README.md                    # Main project documentation
├── .env.example                 # Environment variables template
└── Hydrophone.py               # 🚀 MAIN SCRIPT - Hydrophone Dashboard Generator
```

## 🎯 Key Improvements

### 1. **Separated Location Mappings** 📍
- **File**: `src/hydrophonedashboard/config/location_mappings.py`
- **Purpose**: Clean separation of divert email location names to hydrophone codes
- **Features**:
  - Well-documented mapping system
  - Helper functions for validation and lookup
  - System classification (SoG DDS, NC-DDS, Saanich DDS)
  - ODP site identification
  - Mapping completeness validation

### 2. **Modular Package Structure** 📦
- **Core Package**: `src/hydrophonedashboard/`
- **Config Module**: Settings and mappings
- **Divert Module**: Gmail integration and parsing
- **Utils Module**: Discovery tools and helpers

### 3. **Standalone Scripts** 🔧
- **Location Discovery**: `scripts/list_locations.py`
- **Testing & Validation**: `scripts/test_mappings.py`
- Clean imports using the organized package structure

## 🔧 Usage Examples

### Running the Main Dashboard
```bash
# Generate the hydrophone monitoring dashboard
python Hydrophone.py

# Output: Hydrophone.html (interactive dashboard)
```

### Import Location Mappings
```python
from hydrophonedashboard.config.location_mappings import (
    LOCATION_MAPPING,
    get_hydrophone_codes,
    validate_mapping
)

# Get hydrophone codes for a location
codes = get_hydrophone_codes('ODP 1027')
# Returns: ['CBCH.H1', 'CBCH.H2', 'CBCH.H3', 'CBCH.H4']

# Validate mappings
validation = validate_mapping()
print(f"Mapping completeness: {validation['mapping_completeness']:.1%}")
```

### Use Gmail Divert Parser
```python
from hydrophonedashboard.divert.gmail_parser import GmailDivertParser

parser = GmailDivertParser()
parser.authenticate()
status = parser.update_divert_status(days_back=7)
```

### Run Location Discovery
```python
from hydrophonedashboard.utils.location_discovery import list_hydrophone_locations

locations = list_hydrophone_locations()
print(f"Found {len(locations)} locations")
```

## 📊 Location Mapping Status

### Current ODP Sites Mapped:
- ✅ **ODP 1027C** → `CBCH.H1-H4` (Cascadia Basin)
- ✅ **ODP 1364A** → `CQSH.H1-H4` (Clayoquot Slope) 
- ✅ **ODP 1026** → `NC27.H3-H4` (NC27 array)
- ❌ **ODP 889** → Not yet identified

### Divert Systems Supported:
- **SoG DDS**: Strait of Georgia (3 locations)
- **NC-DDS**: Northern Canadian (5 locations) 
- **Saanich DDS**: Saanich Inlet (1 location)

## 🧪 Testing

Run the test suite to validate the organized structure:

```bash
# Test location mappings and parser
python scripts/test_mappings.py

# Test location discovery
python scripts/list_locations.py

# Validate mappings directly
python -m hydrophonedashboard.config.location_mappings
```

## 🚀 Migration Notes

### Migration Status:
1. **Hydrophone.py**: ✅ **UPDATED** - Now uses organized package imports
2. **Test scripts**: ✅ **UPDATED** - All scripts organized and working
3. **Environment setup**: ✅ **COMPLETE** - Package imports configured

### Benefits of New Structure:
- ✅ **Maintainability**: Clear separation of concerns
- ✅ **Extensibility**: Easy to add new modules
- ✅ **Testing**: Isolated components for unit testing
- ✅ **Documentation**: Self-documenting package structure
- ✅ **Reusability**: Components can be imported independently

## 📝 Development Workflow

1. **Edit location mappings**: Modify `src/hydrophonedashboard/config/location_mappings.py`
2. **Test changes**: Run `python scripts/test_mappings.py`
3. **Validate discovery**: Run `python scripts/list_locations.py`
4. **Update main script**: Modify imports in `Hydrophone.py`

## ✅ Project Status: FULLY ORGANIZED

**Main Script**: `Hydrophone.py` - ✅ **Ready to use** with organized imports
**Package Structure**: ✅ **Complete** - All modules organized and working  
**Location Mappings**: ✅ **91.7% complete** (22/24 locations mapped)
**Divert Integration**: ✅ **Fully functional** with Gmail API
**Testing Suite**: ✅ **All tests passing**

This organization provides a solid foundation for continued development and maintenance of the hydrophone monitoring system! 