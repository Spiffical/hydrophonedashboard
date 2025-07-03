"""
Divert monitoring module for hydrophone dashboard.

Handles Gmail API integration for parsing divert status emails and 
mapping email locations to hydrophone location codes.
"""

from .gmail_parser import GmailDivertParser

__all__ = ['GmailDivertParser'] 