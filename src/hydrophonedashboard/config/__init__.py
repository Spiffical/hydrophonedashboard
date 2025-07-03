"""
Configuration module for hydrophone dashboard.

Contains location mappings, settings, and configuration constants.
"""

from .location_mappings import LOCATION_MAPPING, get_hydrophone_codes, validate_mapping

__all__ = ['LOCATION_MAPPING', 'get_hydrophone_codes', 'validate_mapping'] 