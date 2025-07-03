"""
Hydrophone Dashboard - ONC Data Monitoring System

A comprehensive monitoring system for Ocean Networks Canada (ONC) hydrophone data availability
with integration for Gmail-based divert status monitoring.

Features:
- Real-time hydrophone data availability monitoring  
- Gmail API integration for divert status tracking
- Dashboard generation with status visualization
- Location discovery and mapping utilities
- Automated status classification (good/warning/critical/diverted)

Author: Spencer Bialek
"""

__version__ = "1.0.0"
__author__ = "Spencer Bialek"

# Import available components
from .divert.gmail_parser import GmailDivertParser
from .config.location_mappings import LOCATION_MAPPING

__all__ = [
    'GmailDivertParser',
    'LOCATION_MAPPING'
] 