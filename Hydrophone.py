# -*- coding: utf-8 -*-
"""
Hydrophone Dashboard - Main Script
Ocean Networks Canada (ONC) Hydrophone Data Availability Monitor

Created on Wed Jan 25 17:13:21 2023
@author: aovbui
Enhanced with data availability monitoring and Gmail divert integration

This is the main script for generating the hydrophone monitoring dashboard.
It monitors data availability across all ONC hydrophones and integrates
with Gmail divert notifications to distinguish between data issues and
intentional diversions.

Usage:
    python Hydrophone.py

Outputs:
    - Hydrophone.html: Interactive dashboard with status visualization
    - Console output: Summary of monitoring results
"""

import psycopg2
import pandas as pd
from onc.onc import ONC
from datetime import datetime
from datetime import timedelta
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor
import re
import os
from dotenv import load_dotenv

# Import Gmail divert parser from organized package structure
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from hydrophonedashboard.divert.gmail_parser import GmailDivertParser
    GMAIL_AVAILABLE = True
except ImportError as e:
    print(f"Gmail parser not available: {e}")
    GMAIL_AVAILABLE = False

# Load environment variables from .env file
load_dotenv()

# Get configuration from environment variables
token = os.getenv('ONC_TOKEN')
if not token:
    raise ValueError("ONC_TOKEN not found in environment variables. Please check your .env file.")

onc = ONC(token)
Days = int(os.getenv('DAYS_TO_FETCH', 30))
PlotHeight = int(os.getenv('PLOT_HEIGHT', 400))
DeviceType = os.getenv('DEVICE_TYPE', 'Hydrophones')

# Calculate datefrom dynamically based on Days
datefrom = (datetime.now() - timedelta(days=Days)).strftime('%Y-%m-%dT%H:%M:%S.000Z')

Hier=datetime.today()- timedelta(days = 1)
Yesterday=datetime.strftime(Hier, '%d-%b-%Y')

# Data availability monitoring settings
DATA_TYPES = ['wav', 'fft', 'mp3', 'flac', 'mat']  # All possible types
CRITICAL_DATA_TYPES = ['fft', 'flac', 'mat']  # Most important for monitoring (universal fallback)
MAX_DAYS_WITHOUT_DATA = int(os.getenv('MAX_DAYS_WITHOUT_DATA', 1))  # Alert if no data for more than N days
CHECK_LAST_N_DAYS = int(os.getenv('CHECK_LAST_N_DAYS', 7))      # Check the last N days for data availability

# Gmail divert monitoring settings
ENABLE_DIVERT_MONITORING = os.getenv('ENABLE_DIVERT_MONITORING', 'true').lower() == 'true'
GMAIL_CREDENTIALS_PATH = os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials.json')
GMAIL_TOKEN_PATH = os.getenv('GMAIL_TOKEN_PATH', 'token.json')
DIVERT_CHECK_DAYS = int(os.getenv('DIVERT_CHECK_DAYS', 7))  # How many days back to check for divert emails

# Device-specific capabilities based on historical analysis
# Different hydrophones have different hardware/firmware capabilities
DEVICE_CAPABILITIES = {
    # Device-specific overrides for known limitations
    'ICLISTENHF1354': ['fft'],  # BIIP - only FFT capability
    'ICLISTENHF1561': ['fft', 'flac'],  # CCIP - no MAT capability
    
    # JASCO devices (different architecture) - no FFT capability
    'JASCOAMARHYDROPHONEE000186': ['flac', 'mat'],  # ECHO3.H1
    'JASCOAMARHYDROPHONED001022': ['flac', 'mat'],  # ECHO3.H2  
    'JASCOAMARHYDROPHONED001025': ['flac', 'mat'],  # ECHO3.H3
    'JASCOAMARHYDROPHONEE000029': ['flac', 'mat'],  # ECHO3.H4
    
    # Default for most Ocean Sonics icListen devices: all three types
    # (devices not listed above will use the fallback CRITICAL_DATA_TYPES)
}

def get_expected_data_types(device_code):
    """Get the expected data types for a specific device based on its capabilities."""
    # Check for exact device match first
    if device_code in DEVICE_CAPABILITIES:
        return DEVICE_CAPABILITIES[device_code]
    
    # Default fallback - most devices support all three types
    return CRITICAL_DATA_TYPES

def check_data_availability(device_code, location_code, search_tree_node_id, divert_parser=None):
    """
    Efficiently check data availability for a hydrophone over the last N days
    Returns status information including missing data types and days since last data
    Now includes divert status information to distinguish between data issues and intentional diversions
    """
    status = {
        'overall_status': 'good',
        'days_since_last_data': 0,
        'missing_data_types': [],
        'total_missing_days': 0,
        'status_message': '',
        'last_data_date': None,
        'divert_status': None,  # Will contain divert information if available
        'is_diverted': False,   # Quick boolean check
        'divert_since': None    # When divert started
    }
    
    try:
        current_date = datetime.now()
        
        # Check divert status first
        if divert_parser:
            divert_info = divert_parser.get_location_divert_info(location_code)
            if divert_info:
                status['divert_status'] = divert_info
                status['is_diverted'] = divert_info['status'] == 'Divert'
                status['divert_since'] = divert_info['timestamp'].strftime('%Y-%m-%d %H:%M') if divert_info['timestamp'] else 'Unknown'
        
        # Single API call for all extensions and the entire date range
        date_from = (current_date - timedelta(days=CHECK_LAST_N_DAYS)).strftime('%Y-%m-%dT00:00:00.000Z')
        date_to = current_date.strftime('%Y-%m-%dT23:59:59.000Z')
        
        # Get device-specific expected data types
        expected_data_types = get_expected_data_types(device_code)
        
        # Make separate API calls for each expected data type (ONC API doesn't support comma-separated extensions)
        all_files = []
        try:
            for ext in expected_data_types:
                try:
                    api_response = onc.getListByDevice({
                        'deviceCode': device_code,
                        'dateFrom': date_from,
                        'dateTo': date_to,
                        'extension': ext
                    })
                    
                    # Extract the actual files array from the API response
                    if isinstance(api_response, dict) and 'files' in api_response:
                        all_files.extend(api_response['files'])
                    elif api_response:
                        all_files.extend(api_response if isinstance(api_response, list) else [api_response])
                        
                except Exception as e:
                    print(f"    API error for {device_code} extension {ext}: {e}")
                    continue
                    
        except Exception as e:
            print(f"    General API error for {device_code}: {e}")
            status['overall_status'] = 'error'
            status['status_message'] = f"API error: {str(e)}"
            return status
        
        # Enhanced analysis: Count files by date and type for percentage-based analysis
        files_by_date_and_type = {}
        last_data_found = None
        
        if all_files and len(all_files) > 0:
            for file_info in all_files:
                # Handle both string filenames and objects
                filename = ''
                if isinstance(file_info, str):
                    filename = file_info
                elif isinstance(file_info, dict):
                    filename = file_info.get('filename', '')
                
                # Extract date from filename or dateFrom
                file_date = None
                if isinstance(file_info, dict) and 'dateFrom' in file_info:
                    file_date = datetime.fromisoformat(file_info['dateFrom'].replace('Z', '+00:00')).date()
                elif filename:
                    # Try to extract date from filename pattern
                    try:
                        # Common ONC filename pattern: YYYYMMDDTHHMMSS or YYYYMMDD
                        date_match = re.search(r'(\d{8})', filename)
                        if date_match:
                            date_str = date_match.group(1)
                            file_date = datetime.strptime(date_str, '%Y%m%d').date()
                    except:
                        continue
                
                if file_date:
                    date_str = file_date.strftime('%Y-%m-%d')
                    if date_str not in files_by_date_and_type:
                        files_by_date_and_type[date_str] = {}
                    
                    # Determine file type from filename extension and count files
                    if filename and '.' in filename:
                        # Extract extension from filename
                        ext = filename.split('.')[-1].lower()
                        if ext in expected_data_types:
                            if ext not in files_by_date_and_type[date_str]:
                                files_by_date_and_type[date_str][ext] = 0
                            files_by_date_and_type[date_str][ext] += 1
                            
                            if last_data_found is None or file_date > last_data_found:
                                last_data_found = file_date
        
        # Enhanced percentage-based analysis for data coverage
        # First, establish expected file counts by analyzing available data
        file_counts_by_type = {dtype: [] for dtype in expected_data_types}
        for date_data in files_by_date_and_type.values():
            for dtype in expected_data_types:
                if dtype in date_data and date_data[dtype] > 0:
                    file_counts_by_type[dtype].append(date_data[dtype])
        
        # Calculate expected files per day (use median of days with data)
        expected_files_per_day = {}
        for dtype in expected_data_types:
            if file_counts_by_type[dtype]:
                # Use median as it's more robust to outliers
                sorted_counts = sorted(file_counts_by_type[dtype])
                median_count = sorted_counts[len(sorted_counts)//2]
                # Set minimum expectation (at least a few files per day for continuous recording)
                expected_files_per_day[dtype] = max(median_count, 4)  # At least 4 files per day
            else:
                expected_files_per_day[dtype] = 12  # Default assumption: 12 files per day (every 2 hours)
        
        print(f"      Expected files per day: {expected_files_per_day}")
        
        # Analyze each day using percentage coverage instead of binary presence
        coverage_threshold = 0.3  # 30% coverage to consider day as having "adequate" data
        all_missing_types = set(expected_data_types)
        days_with_poor_coverage = 0
        days_missing_per_type = {dtype: 0 for dtype in expected_data_types}
        coverage_per_type = {dtype: [] for dtype in expected_data_types}
        
        for days_ago in range(CHECK_LAST_N_DAYS):
            check_date = current_date.date() - timedelta(days=days_ago)
            date_str = check_date.strftime('%Y-%m-%d')
            
            day_coverage_info = []
            day_has_adequate_coverage = False
            
            if date_str in files_by_date_and_type:
                date_data = files_by_date_and_type[date_str]
                
                for dtype in expected_data_types:
                    actual_files = date_data.get(dtype, 0)
                    expected_files = expected_files_per_day[dtype]
                    coverage_pct = (actual_files / expected_files) * 100
                    coverage_per_type[dtype].append(coverage_pct)
                    
                    if coverage_pct >= (coverage_threshold * 100):
                        day_coverage_info.append(f"{dtype}({coverage_pct:.0f}%)")
                        all_missing_types.discard(dtype)  # Remove from missing if we've seen adequate coverage
                        day_has_adequate_coverage = True
                    else:
                        days_missing_per_type[dtype] += 1
                        if coverage_pct > 0:
                            day_coverage_info.append(f"{dtype}({coverage_pct:.0f}%)")
                
                print(f"      {date_str}: {', '.join(day_coverage_info) if day_coverage_info else 'NO DATA'}")
            else:
                # No data at all for this day
                for dtype in expected_data_types:
                    days_missing_per_type[dtype] += 1
                    coverage_per_type[dtype].append(0)
                print(f"      {date_str}: NO DATA")
            
            if not day_has_adequate_coverage:
                days_with_poor_coverage += 1
        
        # Determine which types are frequently missing (missing more than 50% of days)
        frequently_missing_types = []
        for dtype, missing_days in days_missing_per_type.items():
            if missing_days > CHECK_LAST_N_DAYS // 2:  # Missing more than half the days
                frequently_missing_types.append(dtype)
        
        # Calculate overall coverage statistics
        overall_coverage_per_type = {}
        for dtype in expected_data_types:
            if coverage_per_type[dtype]:
                avg_coverage = sum(coverage_per_type[dtype]) / len(coverage_per_type[dtype])
                overall_coverage_per_type[dtype] = avg_coverage
            else:
                overall_coverage_per_type[dtype] = 0
        
        # Update status with enhanced percentage-based metrics
        status['missing_data_types'] = frequently_missing_types
        status['total_missing_days'] = days_with_poor_coverage
        status['days_missing_per_type'] = days_missing_per_type
        status['coverage_per_type'] = overall_coverage_per_type
        status['expected_files_per_day'] = expected_files_per_day
        
        if last_data_found:
            status['days_since_last_data'] = (current_date.date() - last_data_found).days
            status['last_data_date'] = last_data_found.strftime('%Y-%m-%d')
        else:
            status['days_since_last_data'] = CHECK_LAST_N_DAYS
        
        # Enhanced status determination: Focus on recent trends (last 3 days) with percentage analysis
        recent_days = 3  
        recent_missing_per_type = {dtype: 0 for dtype in expected_data_types}
        recent_days_with_poor_coverage = 0
        
        # Count poor coverage in recent days only
        for days_ago in range(recent_days):
            check_date = current_date.date() - timedelta(days=days_ago)
            date_str = check_date.strftime('%Y-%m-%d')
            
            day_has_adequate_coverage = False
            
            if date_str in files_by_date_and_type:
                date_data = files_by_date_and_type[date_str]
                
                for dtype in expected_data_types:
                    actual_files = date_data.get(dtype, 0)
                    expected_files = expected_files_per_day[dtype]
                    coverage_pct = (actual_files / expected_files) * 100
                    
                    if coverage_pct >= (coverage_threshold * 100):
                        day_has_adequate_coverage = True
                    else:
                        recent_missing_per_type[dtype] += 1
            else:
                for dtype in expected_data_types:
                    recent_missing_per_type[dtype] += 1
            
            if not day_has_adequate_coverage:
                recent_days_with_poor_coverage += 1
        
        # Calculate recent trends using percentage-based analysis
        frequently_missing_recent = [dtype for dtype, missing_days in recent_missing_per_type.items() 
                                   if missing_days >= 2]  # Missing 2+ of last 3 days
        
        # Check if issue appears to be resolved (recent good despite historical issues)
        recent_data_good = recent_days_with_poor_coverage == 0 and len(frequently_missing_recent) == 0
        historical_issues = days_with_poor_coverage >= 3 or len(frequently_missing_types) >= 1
        
        # Enhanced divert analysis: Check historical diversions during analysis period
        divert_explanation = None
        if divert_parser:
            try:
                # Get divert periods during the analysis timeframe
                analysis_start = current_date - timedelta(days=CHECK_LAST_N_DAYS)
                analysis_end = current_date
                
                divert_stats = divert_parser.get_divert_statistics(
                    location_code, 
                    start_date=analysis_start, 
                    end_date=analysis_end
                )
                
                if divert_stats['total_periods'] > 0:
                    divert_percentage = divert_stats['divert_percentage']
                    
                    # Estimate if missing data aligns with divert periods using coverage-based analysis
                    missing_data_percentage = (days_with_poor_coverage / CHECK_LAST_N_DAYS) * 100
                    
                    # Calculate average data coverage deficit
                    total_coverage_deficit = 0
                    for dtype in expected_data_types:
                        avg_coverage = overall_coverage_per_type.get(dtype, 0)
                        coverage_deficit = max(0, 100 - avg_coverage)  # How much coverage is missing
                        total_coverage_deficit += coverage_deficit
                    
                    avg_coverage_deficit = total_coverage_deficit / len(expected_data_types) if expected_data_types else 0
                    
                    # If significant portion of missing data aligns with divert periods
                    if divert_percentage > 5:  # More than 5% of time was diverted
                        # More sophisticated alignment calculation
                        explained_percentage = min(divert_percentage, avg_coverage_deficit)
                        divert_explanation = {
                            'divert_percentage': divert_percentage,
                            'explained_missing': explained_percentage,
                            'avg_coverage_deficit': avg_coverage_deficit,
                            'periods_count': divert_stats['divert_periods_count'],
                            'total_divert_time': divert_stats['total_divert_time']
                        }
                        
                        # Store for status display
                        status['divert_explanation'] = divert_explanation
                        
            except Exception as e:
                print(f"      Error analyzing divert periods: {e}")
        
        # Determine status with enhanced divert-aware logic
        if status['is_diverted']:
            # Location is currently diverted - missing data is expected
            if recent_days_with_poor_coverage >= 1 or len(frequently_missing_recent) >= 1:
                status['overall_status'] = 'diverted'
                status['status_message'] = f"🔄 DIVERTED - Missing data expected (since {status['divert_since']})"
            else:
                status['overall_status'] = 'diverted'
                status['status_message'] = f"🔄 DIVERTED - Data collection suspended (since {status['divert_since']})"
                
        elif divert_explanation and divert_explanation['explained_missing'] > 20:
            # Historical diversions explain significant missing data using coverage analysis
            days_diverted = int((divert_explanation['total_divert_time'].total_seconds() / 86400))
            coverage_deficit = divert_explanation['avg_coverage_deficit']
            
            # Adjust status based on remaining unexplained coverage issues
            unexplained_missing = max(0, days_with_poor_coverage - days_diverted)
            unexplained_recent = recent_days_with_poor_coverage
            
            # Check if recent issues could also be from recent diversions
            recent_start = current_date - timedelta(days=3)
            try:
                recent_divert_stats = divert_parser.get_divert_statistics(
                    location_code, start_date=recent_start, end_date=current_date
                )
                if recent_divert_stats['divert_percentage'] > 15:
                    unexplained_recent = max(0, recent_days_with_poor_coverage - 1)
            except:
                pass
            
            if unexplained_recent >= 2 and unexplained_missing >= 3:
                status['overall_status'] = 'warning'
                status['status_message'] = f"Coverage issues beyond diversions ({days_diverted}d diverted, {coverage_deficit:.1f}% avg deficit)"
            elif unexplained_recent >= 1 or unexplained_missing >= 2:
                status['overall_status'] = 'minor'
                status['status_message'] = f"Minor coverage issues beyond diversions ({days_diverted}d diverted of {CHECK_LAST_N_DAYS}d)"
            else:
                status['overall_status'] = 'good'
                status['status_message'] = f"Coverage gaps explained by diversions ({days_diverted}d diverted, {coverage_deficit:.1f}% deficit)"
                
        elif recent_days_with_poor_coverage >= 3:
            status['overall_status'] = 'critical'
            days_word = 'day' if recent_days_with_poor_coverage == 1 else 'days'
            status['status_message'] = f"Poor data coverage for {recent_days_with_poor_coverage} recent {days_word}"
        elif recent_days_with_poor_coverage >= 2:
            status['overall_status'] = 'warning'
            days_word = 'day' if recent_days_with_poor_coverage == 1 else 'days'
            status['status_message'] = f"Poor data coverage for {recent_days_with_poor_coverage} recent {days_word}"
        elif len(frequently_missing_recent) >= 2:
            status['overall_status'] = 'warning'
            status['status_message'] = f"Recently missing data types: {', '.join(sorted(frequently_missing_recent))}"
        elif len(frequently_missing_recent) >= 1:
            status['overall_status'] = 'minor'
            status['status_message'] = f"Recently missing data type: {', '.join(sorted(frequently_missing_recent))}"
        elif recent_data_good and historical_issues:
            status['overall_status'] = 'good'
            status['status_message'] = "Recently resolved - all data types now available"
        else:
            status['status_message'] = "All expected data types available"
            
    except Exception as e:
        status['overall_status'] = 'error'
        status['status_message'] = f"Error checking data: {str(e)}"
        print(f"Error checking data availability for {device_code}: {e}")
    
    return status

def get_status_color(status):
    """Return CSS color class based on status"""
    colors = {
        'good': '#28a745',      # Green
        'minor': '#ffc107',     # Yellow
        'warning': '#fd7e14',   # Orange
        'critical': '#dc3545',  # Red
        'diverted': '#6f42c1',  # Purple - for intentional diversions
        'error': '#6c757d'      # Gray
    }
    return colors.get(status, '#6c757d')

def get_status_icon(status):
    """Return status icon/symbol"""
    icons = {
        'good': '✓',
        'minor': '⚠',
        'warning': '⚠',
        'critical': '✗',
        'diverted': '🔄',  # Circular arrows for divert
        'error': '?'
    }
    return icons.get(status, '?')

def get_db_connection():
    """Get database connection using environment variables"""
    db_host = os.getenv('DB_HOST')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    if not all([db_host, db_name, db_user, db_password]):
        raise ValueError("Database configuration incomplete. Please check DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD in your .env file.")
    
    return psycopg2.connect(
        host=db_host,
        dbname=db_name,
        user=db_user,
        password=db_password
    )

deviceCategoryCode=['HYDROPHONE']

MyDevices=pd.DataFrame(columns=['locationCode', 'locationName', 'begin', 'deviceCode', 'deviceCategoryCode', 'deviceCategoryID', 'DSURL', 'Depth', 'deviceID', 'deviceName',
                                'siteDeviceID','searchTreeNodeID','dataProductFormatID', 'data_status'])

print("Fetching hydrophone deployments...")
for i in range(len(deviceCategoryCode)):   
    result = onc.getDeployments({'deviceCategoryCode':deviceCategoryCode[i], 'dateFrom': datefrom})     
    for j in range(len(result)):
        if not result[j]['end']:
            myloc=onc.getLocations({'locationCode':result[j]['locationCode']})
            
            oneDevice=pd.DataFrame(data=[[result[j]['locationCode'],myloc[0]['locationName'], result[j]['begin'], result[j]['deviceCode'],result[j]['deviceCategoryCode'], 
                                          myloc[0]['dataSearchURL'],result[j]['depth']]],
                                   columns=['locationCode','locationName', 'begin', 'deviceCode', 'deviceCategoryCode', 'DSURL',  'Depth'])
            MyDevices=pd.concat([MyDevices, oneDevice])
                       
MyDevices=MyDevices.sort_values(by=['locationCode'])
MyDevices=MyDevices.reset_index(drop=True)
        
print("Getting device details...")
for k in range(len(MyDevices)):
    result=onc.getDevices({'deviceCode':MyDevices.deviceCode[k]})
    MyDevices.loc[k, "deviceID"]=result[0]['deviceId']
    MyDevices.loc[k, "deviceName"]=result[0]['deviceName']
   
print("Querying database for device categories...")    
MyDevices['deviceCategoryID']=""
try:
    conn = get_db_connection()
    cur = conn.cursor()
    for l in range(len(MyDevices.deviceID)):
        cur.execute("""SELECT devicecategoryid from device where deviceid ="""+str(MyDevices.deviceID[l]))
        MyDevices.loc[l, 'deviceCategoryID']=str(cur.fetchall()[0][0])
    conn.close()
except Exception as e:
    print(f"Unable to connect to the database: {e}")
    # Skip database operations if connection fails
    print("Skipping database queries - using default values")
    for l in range(len(MyDevices.deviceID)):
        MyDevices.loc[l, 'deviceCategoryID'] = '19'  # Default hydrophone category
    
print("Getting site device IDs...")    
MyDevices['siteDeviceID']=""
try:
    conn = get_db_connection()
    cur = conn.cursor()
    for l in range(len(MyDevices.deviceID)):
        cur.execute("""SELECT sitedeviceid from sitedevice where deviceid = (%s) and datefrom = (%s)""", (str(MyDevices.deviceID[l]), str(MyDevices.begin[l])))
        MyDevices.loc[l, 'siteDeviceID']=cur.fetchall()[0][0]
    conn.close()
except Exception as e:
    print(f"Unable to connect to the database: {e}")
    print("Skipping database queries - using device IDs as site device IDs")
    for l in range(len(MyDevices.deviceID)):
        MyDevices.loc[l, 'siteDeviceID'] = MyDevices.deviceID[l]  # Use device ID as fallback 

print("Getting search tree node IDs...")
MyDevices['searchTreeNodeID']=""
try:
    conn = get_db_connection()
    cur = conn.cursor()
    for l in range(len(MyDevices)):
        cur.execute("""SELECT searchtreenodeid from searchtreenodesitedevice where sitedeviceid ="""+str(MyDevices.siteDeviceID[l]))
        MyDevices.loc[l, 'searchTreeNodeID']=cur.fetchall()[0][0]
    conn.close()
except Exception as e:
    print(f"Unable to connect to the database: {e}")
    print("Skipping database queries - using default search tree node IDs")
    # Use a mapping of known location codes to search tree node IDs as fallback
    location_mapping = {
        'BACNH.H1': '2366', 'BACNH.H2': '2367', 'BACNH.H3': '2368', 'BACNH.H4': '2369',
        'BACUS': '21', 'BIIP': '1943', 'CBCH.H1': '2285', 'CBCH.H2': '2286', 'CBCH.H3': '2287', 'CBCH.H4': '2288'
    }
    for l in range(len(MyDevices)):
        location_code = MyDevices.locationCode[l]
        MyDevices.loc[l, 'searchTreeNodeID'] = location_mapping.get(location_code, '1')  # Default to 1 if not found 

MyDevices['dataProductFormatID']=[[176,53] for l in MyDevices.index]

# Initialize Gmail divert parser
divert_parser = None
if ENABLE_DIVERT_MONITORING and GMAIL_AVAILABLE:
    try:
        print("Initializing Gmail divert monitoring...")
        divert_parser = GmailDivertParser(
            credentials_path=GMAIL_CREDENTIALS_PATH,
            token_path=GMAIL_TOKEN_PATH
        )
        
        # Update divert status from recent emails
        divert_status = divert_parser.update_divert_status(days_back=DIVERT_CHECK_DAYS)
        
        # Print divert summary
        divert_summary = divert_parser.get_divert_summary()
        print(f"Divert monitoring active: {divert_summary['currently_diverted']} locations diverted, "
              f"{divert_summary['events_processed']} events processed")
              
    except Exception as e:
        print(f"Warning: Gmail divert monitoring failed to initialize: {e}")
        print("Continuing without divert monitoring...")
        divert_parser = None
else:
    if not ENABLE_DIVERT_MONITORING:
        print("Divert monitoring disabled in configuration")
    if not GMAIL_AVAILABLE:
        print("Gmail API dependencies not available - install with: pip install -r requirements.txt")

# Check data availability for each device
print("Checking data availability for each hydrophone...")
print("Using parallel processing for faster checks...")

# Initialize the data_status column as object type to store dictionaries
MyDevices['data_status'] = pd.Series([None] * len(MyDevices), dtype=object)

def check_single_device(i):
    """Helper function for parallel processing"""
    device_code = MyDevices.deviceCode[i]
    location_code = MyDevices.locationCode[i]
    search_tree_node_id = MyDevices.searchTreeNodeID[i]
    
    print(f"Checking {location_code} ({device_code})...")
    status = check_data_availability(device_code, location_code, search_tree_node_id, divert_parser)
    print(f"  Status: {status['overall_status']} - {status['status_message']}")
    return i, status

# Use parallel processing with a reasonable number of workers
max_workers = min(8, len(MyDevices))  # Don't overwhelm the API
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    results = list(executor.map(check_single_device, range(len(MyDevices))))

# Update the dataframe with results
for i, status in results:
    MyDevices.at[i, 'data_status'] = status

print("Generating enhanced HTML with data availability indicators...")
    
with open ("Hydrophone.html", 'w') as file:
    file.write('<!DOCTYPE html>'+'\n')
    file.write('<html>'+'\n')
    file.write('<head>'+'\n')
    file.write('\t'+'<meta charset="UTF-8">'+'\n')
    file.write('\t'+'<title>'+DeviceType+' - Data Availability Monitor</title>'+'\n')
    file.write('\t'+'<script src="assets/uPlot.iife.min.js"></script>'+'\n')
    file.write('\t'+'<script src="assets/oncdw.min.js"></script>'+'\n')
    file.write('\t'+'<link rel="stylesheet" href="assets/uPlot.min.css" />'+'\n')
    file.write('\t'+'<link rel="stylesheet" href="assets/oncdw.min.css" />'+'\n')
    file.write('\t'+'<link rel="stylesheet" href="assets/instaboard.css" />'+'\n')
    file.write('\t'+'<style>'+'\n')
    file.write('\t'+'.oncWidgetGroup.gifs { text-align: justify; }'+'\n')
    file.write('\t'+'.oncWidgetGroup.gifs .widgetWrap { display: inline-block; width: auto;  clear: none; margin-right: 5px; }'+'\n')
    file.write('\t'+'.oncWidgetGroup.gifs .contents {  }'+'\n')
    # Add status indicator styles
    file.write('\t'+'.status-indicator { display: inline-block; padding: 4px 8px; border-radius: 4px; color: white; font-weight: bold; font-size: 12px; margin-left: 10px; }'+'\n')
    file.write('\t'+'.status-badge { display: inline-block; padding: 2px 6px; border-radius: 12px; color: white; font-weight: bold; font-size: 11px; margin-left: 5px; }'+'\n')
    file.write('\t'+'.data-status-summary { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; padding: 10px; margin: 10px 0; }'+'\n')
    file.write('\t'+'.status-legend { background: #e9ecef; padding: 10px; border-radius: 6px; margin-bottom: 20px; }'+'\n')
    file.write('\t'+'.status-legend h3 { margin-top: 0; }'+'\n')
    file.write('\t'+'.legend-item { display: inline-block; margin-right: 15px; }'+'\n')
    file.write('\t'+'.sidenav { position: fixed; left: 0; top: 80px; width: 300px; height: calc(100vh - 80px); overflow-y: auto; background: #f8f9fa; padding: 20px; box-shadow: 2px 0 5px rgba(0,0,0,0.1); z-index: 1000; }'+'\n')
    file.write('\t'+'.sidenav a { text-decoration: none; }'+'\n')
    file.write('\t'+'.sidenav h2 { margin-top: 0; margin-bottom: 15px; color: #495057; border-bottom: 2px solid #dee2e6; padding-bottom: 8px; }'+'\n')
    file.write('\t'+'.sidenav .device span:first-child { font-size: 10px; color: #6c757d; font-weight: normal; }'+'\n')
    file.write('\t'+'body { margin-left: 340px; padding: 20px; }'+'\n')
    file.write('\t'+'.main { margin-left: 0; padding: 0; }'+'\n')
    file.write('\t'+'.section-header { border-left: 5px solid; padding-left: 10px; }'+'\n')
    file.write('\t'+'.summary-box { background: #e9ecef; border: 2px solid #6c757d; border-radius: 8px; padding: 15px; margin-bottom: 20px; }'+'\n')
    file.write('\t'+'.summary-counts { display: flex; gap: 15px; margin-top: 10px; }'+'\n')
    file.write('\t'+'.count-item { padding: 5px 10px; border-radius: 4px; font-weight: bold; color: white; }'+'\n')
    # Add widget isolation and error handling styles
    file.write('\t'+'.widget-container { margin: 10px 0; clear: both; }'+'\n')
    file.write('\t'+'.oncWidget.widget-error { border: 2px solid #dc3545; background: #f8d7da; padding: 10px; margin: 5px 0; }'+'\n')
    file.write('\t'+'.oncWidget.widget-error::before { content: "⚠ Widget Loading Error"; display: block; color: #721c24; font-weight: bold; margin-bottom: 5px; }'+'\n')
    file.write('\t'+'.widget-error-indicator { background: #f8d7da; border: 1px solid #dc3545; padding: 5px; margin: 5px 0; border-radius: 4px; color: #721c24; font-size: 12px; }'+'\n')
    file.write('\t'+'</style>'+'\n')
    # Add JavaScript error handling and widget isolation
    file.write('\t'+'<script>'+'\n')
    file.write('\t'+'// Prevent widget cascade failures by isolating each widget'+'\n')
    file.write('\t'+'(function() {'+'\n')
    file.write('\t'+'\t'+'// Override console.error to catch widget errors'+'\n')
    file.write('\t'+'\t'+'const originalError = console.error;'+'\n')
    file.write('\t'+'\t'+'console.error = function(...args) {'+'\n')
    file.write('\t'+'\t'+'\t'+'// Log the error but don\'t let it break subsequent widgets'+'\n')
    file.write('\t'+'\t'+'\t'+'originalError.apply(console, args);'+'\n')
    file.write('\t'+'\t'+'};'+'\n')
    file.write('\t'+'\t'+''+'\n')
    file.write('\t'+'\t'+'// Add global error handler'+'\n')
    file.write('\t'+'\t'+'window.addEventListener("error", function(e) {'+'\n')
    file.write('\t'+'\t'+'\t'+'console.log("Widget error caught and isolated:", e.message);'+'\n')
    file.write('\t'+'\t'+'\t'+'return true; // Prevent error from bubbling'+'\n')
    file.write('\t'+'\t'+'});'+'\n')
    file.write('\t'+'\t'+''+'\n')
    file.write('\t'+'\t'+'// Initialize widgets with error boundaries'+'\n')
    file.write('\t'+'\t'+'document.addEventListener("DOMContentLoaded", function() {'+'\n')
    file.write('\t'+'\t'+'\t'+'// Add progressive widget loading with delays'+'\n')
    file.write('\t'+'\t'+'\t'+'const widgetContainers = document.querySelectorAll(".widget-container");'+'\n')
    file.write('\t'+'\t'+'\t'+''+'\n')
    file.write('\t'+'\t'+'\t'+'widgetContainers.forEach(function(container, index) {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'setTimeout(function() {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'try {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'// Trigger widget initialization for this container only'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'const widgets = container.querySelectorAll(".oncWidget");'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'widgets.forEach(function(widget) {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'// Force re-scan of this specific widget'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'if (window.oncdw && widget.getAttribute("data-widget")) {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'try {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'window.oncdw.scan(widget);'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'} catch(e) {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'console.log("Widget scan failed for:", widget.id, e);'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'}'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'}'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'});'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'} catch(e) {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'console.log("Container widget init failed:", container.id, e);'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'}'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'}, index * 500); // Stagger widget loading'+'\n')
    file.write('\t'+'\t'+'\t'+'});'+'\n')
    file.write('\t'+'\t'+'\t'+''+'\n')
    file.write('\t'+'\t'+'\t'+'// Check for failed widgets and mark them'+'\n')
    file.write('\t'+'\t'+'\t'+'setTimeout(function() {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'const widgets = document.querySelectorAll(".oncWidget");'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'widgets.forEach(function(widget) {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'if (widget.innerHTML.trim() === "" || widget.textContent.includes("No data preview image could be found")) {'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'const errorDiv = document.createElement("div");'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'errorDiv.className = "widget-error-indicator";'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'errorDiv.textContent = "⚠ No data available for this widget";'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'widget.parentNode.insertBefore(errorDiv, widget.nextSibling);'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'\t'+'widget.style.display = "none";'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'\t'+'}'+'\n')
    file.write('\t'+'\t'+'\t'+'\t'+'});'+'\n')
    file.write('\t'+'\t'+'\t'+'}, 12000);'+'\n')
    file.write('\t'+'\t'+'});'+'\n')
    file.write('\t'+'})();'+'\n')
    file.write('\t'+'</script>'+'\n')
    file.write('</head>'+'\n')
    file.write('<body>'+'\n')
    file.write('\t'+'<data id="oncdw" data-token="'+ token+'"></data>'+'\n')
    file.write('\t'+'<h1>'+DeviceType+' - Data Availability Monitor</h1>'+'\n')
    
    # Add status legend
    file.write('\t'+'<div class="status-legend">'+'\n')
    file.write('\t'+'\t'+'<h3>Status Legend</h3>'+'\n')
    file.write('\t'+'\t'+'<div class="legend-item"><span class="status-badge" style="background-color: #28a745;">✓ Good</span> All data types available</div>'+'\n')
    file.write('\t'+'\t'+'<div class="legend-item"><span class="status-badge" style="background-color: #ffc107;">⚠ Minor</span> Some data types missing</div>'+'\n')
    file.write('\t'+'\t'+'<div class="legend-item"><span class="status-badge" style="background-color: #fd7e14;">⚠ Warning</span> Multiple data types missing or 1-2 days without data</div>'+'\n')
    file.write('\t'+'\t'+'<div class="legend-item"><span class="status-badge" style="background-color: #dc3545;">✗ Critical</span> No data for 3+ days</div>'+'\n')
    file.write('\t'+'\t'+'<div class="legend-item"><span class="status-badge" style="background-color: #6f42c1;">🔄 Diverted</span> Data collection suspended by diversion</div>'+'\n')
    file.write('\t'+'</div>'+'\n')
    
    # Calculate status counts for summary
    critical_count = sum(1 for i in range(len(MyDevices)) if MyDevices.data_status[i]['overall_status'] == 'critical')
    warning_count = sum(1 for i in range(len(MyDevices)) if MyDevices.data_status[i]['overall_status'] == 'warning')
    minor_count = sum(1 for i in range(len(MyDevices)) if MyDevices.data_status[i]['overall_status'] == 'minor')
    diverted_count = sum(1 for i in range(len(MyDevices)) if MyDevices.data_status[i]['overall_status'] == 'diverted')
    good_count = len(MyDevices) - critical_count - warning_count - minor_count - diverted_count
    
    # Add summary box
    file.write('\t'+'<div class="summary-box">'+'\n')
    file.write('\t'+'\t'+'<h3>📊 System Status Summary</h3>'+'\n')
    hydrophone_word = 'hydrophone' if len(MyDevices) == 1 else 'hydrophones'
    file.write('\t'+'\t'+'<p>Monitoring <strong>'+str(len(MyDevices))+' '+hydrophone_word+'</strong> across the ocean network. Status overview:</p>'+'\n')
    file.write('\t'+'\t'+'<div class="summary-counts">'+'\n')
    file.write('\t'+'\t'+'\t'+'<div class="count-item" style="background-color: #28a745;">'+str(good_count)+' Good</div>'+'\n')
    minor_issues_word = 'Minor Issue' if minor_count == 1 else 'Minor Issues'
    file.write('\t'+'\t'+'\t'+'<div class="count-item" style="background-color: #ffc107;">'+str(minor_count)+' '+minor_issues_word+'</div>'+'\n')
    file.write('\t'+'\t'+'\t'+'<div class="count-item" style="background-color: #fd7e14;">'+str(warning_count)+' Warnings</div>'+'\n')
    file.write('\t'+'\t'+'\t'+'<div class="count-item" style="background-color: #dc3545;">'+str(critical_count)+' Critical</div>'+'\n')
    file.write('\t'+'\t'+'\t'+'<div class="count-item" style="background-color: #6f42c1;">'+str(diverted_count)+' Diverted</div>'+'\n')
    file.write('\t'+'\t'+'</div>'+'\n')
    if critical_count + warning_count + minor_count > 0:
        attention_count = critical_count + warning_count + minor_count
        attention_word = 'hydrophone needs' if attention_count == 1 else 'hydrophones need'
        devices_word = 'device' if critical_count == 1 else 'devices'
        file.write('\t'+'\t'+'<p><strong>Action Required:</strong> '+str(attention_count)+' '+attention_word+' attention. Critical '+devices_word+' may have complete data outages.</p>'+'\n')
    else:
        file.write('\t'+'\t'+'<p><strong>✅ All systems operational</strong> - No issues detected across the hydrophone network.</p>'+'\n')
    if diverted_count > 0:
        diverted_word = 'hydrophone is' if diverted_count == 1 else 'hydrophones are'
        file.write('\t'+'\t'+'<p><strong>ℹ️ Divert Status:</strong> '+str(diverted_count)+' '+diverted_word+' intentionally diverted. Missing data is expected.</p>'+'\n')
    file.write('\t'+'</div>'+'\n')
    
    file.write('\t'+'<div class="sidenav">'+'\n')
    file.write('\t'+'<h2>📍 Hydrophone Sites</h2>'+'\n')
    file.write('\t'+'<ul class="nav">'+'\n')
    file.write('\t'+'<li>'+'\n')
    
    # Use consistent ID counters to avoid duplicates
    section_counter = 0
    widget_counter = 0
    
    for i in range(len(MyDevices.locationCode)):
         status = MyDevices.data_status[i]
         status_color = get_status_color(status['overall_status'])
         status_icon = get_status_icon(status['overall_status'])
         
         file.write('\t'+'<a href="#section_'+str(section_counter)+'"><span class="device"><span>Site</span>'+MyDevices.locationCode[i]+'</span>'+
                   '<span class="status-badge" style="background-color: '+status_color+';">'+status_icon+'</span></a>'+'\n')
         file.write('\t'+'<ul>'+'\n')
         DF=MyDevices[MyDevices.locationCode==MyDevices.locationCode[i]]
         DF=DF.reset_index(drop=True)
         for h in range(len(DF)):
             file.write('\t'+'\t'+'<li><a href="#widget_group_'+str(widget_counter)+'"><span class="sensor"><span>'+str(DF.deviceID[h])+'</span>'+DF.deviceName[h]+'</span></a></li>'+'\n')
             widget_counter += 1
         file.write('\t'+'</ul>'+'\n')    
         file.write('\t'+'</li>'+'\n')
         section_counter += 1
    file.write('\t'+'</div>'+'\n')
    file.write('\n')
    
    # Reset counters for main content (but keep them separate)
    section_counter = 0
    widget_counter = 0
    
    file.write('\t'+'<div class="main">'+'\n')
    for i in range(len(MyDevices.locationCode)): 
            status = MyDevices.data_status[i]
            status_color = get_status_color(status['overall_status'])
            status_icon = get_status_icon(status['overall_status'])
            
            file.write('\n')
            file.write('\t'+'<div class="section" id="section_'+str(section_counter)+'">'+'\n')
            file.write('\t'+'<div class="section-header" style="border-color: '+status_color+';">'+'\n')
            file.write('\t'+'<h2>'+MyDevices.locationCode[i]+ " - "+MyDevices.locationName[i]+'. Depth: '+str(MyDevices.Depth[i])+' m'+
                      '<span class="status-indicator" style="background-color: '+status_color+';">'+status_icon+' '+status['overall_status'].upper()+'</span></h2>'+'\n')
            file.write('\t'+'</div>'+'\n')
            
            # Add data status summary
            file.write('\t'+'<div class="data-status-summary">'+'\n')
            file.write('\t'+'\t'+'<strong>Data Status:</strong> '+status['status_message']+'<br>'+'\n')
            
            # Add enhanced divert information if available
            if status['is_diverted']:
                file.write('\t'+'\t'+'<strong>🔄 Divert Status:</strong> ACTIVE - Data collection suspended since '+status['divert_since']+'<br>'+'\n')
                if status['divert_status'] and status['divert_status'].get('system'):
                    file.write('\t'+'\t'+'<strong>Divert System:</strong> '+status['divert_status']['system']+'<br>'+'\n')
            elif status.get('divert_explanation'):
                # Show enhanced historical divert explanation with coverage analysis  
                divert_info = status['divert_explanation']
                days_diverted = int((divert_info['total_divert_time'].total_seconds() / 86400))
                coverage_deficit = divert_info.get('avg_coverage_deficit', 0)
                days_word1 = 'day' if days_diverted == 1 else 'days'
                days_word2 = 'day' if CHECK_LAST_N_DAYS == 1 else 'days'
                file.write('\t'+'\t'+'<strong>📊 Divert History:</strong> '+str(days_diverted)+' '+days_word1+' diverted in last '+str(CHECK_LAST_N_DAYS)+' '+days_word2+' ('+f"{divert_info['divert_percentage']:.1f}%"+')<br>'+'\n')
                file.write('\t'+'\t'+'<strong>Coverage Analysis:</strong> '+f"{coverage_deficit:.1f}% avg coverage deficit"+', '+f"{divert_info['explained_missing']:.1f}%"+' explained by diversions<br>'+'\n')
            
            if status['last_data_date']:
                days_ago_word = 'day' if status['days_since_last_data'] == 1 else 'days'
                file.write('\t'+'\t'+'<strong>Last Data:</strong> '+status['last_data_date']+' ('+str(status['days_since_last_data'])+' '+days_ago_word+' ago)<br>'+'\n')
            # Enhanced coverage details display
            if status.get('coverage_per_type'):
                coverage_details = []
                for dtype in status.get('expected_files_per_day', {}).keys():
                    avg_coverage = status['coverage_per_type'].get(dtype, 0)
                    missing_days = status['days_missing_per_type'].get(dtype, 0)
                    expected_files = status['expected_files_per_day'].get(dtype, 0)
                    
                    if avg_coverage < 90:  # Show details for types with <90% coverage
                        poor_days_word = 'day' if missing_days == 1 else 'days' 
                        coverage_details.append(f"{dtype} ({avg_coverage:.0f}% avg coverage, {missing_days}/{CHECK_LAST_N_DAYS} poor {poor_days_word})")
                    elif missing_days > 0:
                        coverage_details.append(f"{dtype} ({avg_coverage:.0f}% avg coverage)")
                
                if coverage_details:
                    file.write('\t'+'\t'+'<strong>Data Coverage Analysis:</strong> '+', '.join(coverage_details)+'<br>'+'\n')
            elif status['missing_data_types']:
                file.write('\t'+'\t'+'<strong>Missing Data Types:</strong> '+', '.join(status['missing_data_types'])+'<br>'+'\n')
                
            # Enhanced coverage analysis display with divert awareness
            if status['is_diverted']:
                file.write('\t'+'\t'+'<strong>Note:</strong> Poor coverage expected due to active diversion\n')
            elif status.get('divert_explanation'):
                divert_info = status['divert_explanation']
                days_diverted = int((divert_info['total_divert_time'].total_seconds() / 86400))
                coverage_deficit = divert_info.get('avg_coverage_deficit', 0)
                unexplained_days = max(0, status['total_missing_days'] - days_diverted)
                
                if unexplained_days > 0:
                    total_days_word = 'day' if status['total_missing_days'] == 1 else 'days'
                    diverted_days_word = 'day' if days_diverted == 1 else 'days' 
                    unexplained_days_word = 'day' if unexplained_days == 1 else 'days'
                    file.write('\t'+'\t'+'<strong>Coverage Analysis:</strong> '+str(status['total_missing_days'])+' poor coverage '+total_days_word+' ('+str(days_diverted)+' '+diverted_days_word+' diverted + '+str(unexplained_days)+' unexplained '+unexplained_days_word+'), '+f"{coverage_deficit:.1f}% avg deficit\n")
                else:
                    total_days_word = 'day' if status['total_missing_days'] == 1 else 'days'
                    file.write('\t'+'\t'+'<strong>Coverage Analysis:</strong> '+str(status['total_missing_days'])+' poor coverage '+total_days_word+' - explained by diversions, '+f"{coverage_deficit:.1f}% avg deficit\n")
            else:
                total_days_word = 'day' if status['total_missing_days'] == 1 else 'days'
                check_days_word = 'day' if CHECK_LAST_N_DAYS == 1 else 'days'
                file.write('\t'+'\t'+'<strong>Coverage Analysis:</strong> '+str(status['total_missing_days'])+' poor coverage '+total_days_word+' out of '+str(CHECK_LAST_N_DAYS)+' '+check_days_word+'\n')
            file.write('\t'+'</div>'+'\n')
            
            # Widget Group 1: Archive Map with unique ID and error handling boundary
            file.write('\t'+'<div class="widget-container" id="widget_group_'+str(widget_counter)+'">'+'\n')
            file.write('\t'+'\t'+'<p><a href="http://data.oceannetworks.ca/DeviceListing?DeviceId='+str(MyDevices.deviceID[i])+'" target="_blank">Device Details </a>'+ '</a>and </a>' 
                       +'<a href="'+MyDevices.DSURL[i]+'" target="_blank">Data Search </a>'+ '</a>and </a>' +
                       '<a href="https://data.oceannetworks.ca/SearchHydrophoneData?LOCATION='+str(MyDevices.searchTreeNodeID[i])+'&DEVICE='+str(MyDevices.deviceID[i])+'&DATE='+Yesterday+'" target="_blank">Search Hydrophone </a></p>'+'\n')
            
            # Archive Map Widget with error boundaries
            file.write('\t'+'\t'+'<section class="oncWidgetGroup archive-map-group">'+'\n')
            file.write('\t'+'\t'+'\t'+'<div class="widgetWrap wgArchiveMap">'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'<div class="device"><span>'+str(MyDevices.deviceID[i])+'</span>'+MyDevices.deviceName[i]+'</div>'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'<div class="clear"></div>'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'<section class="oncWidget widget-isolated" id="archiveMap_'+str(widget_counter)+'"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'data-widget="archiveMap"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'data-widget-id="archiveMap_'+str(widget_counter)+'"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'dateFrom="minus'+str(Days)+'d"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'dateTo="midnight"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'deviceCode="'+str(MyDevices.deviceCode[i])+'"'+'\n')  
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'options="height: '+str(PlotHeight)+'"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'extension="wav, fft, mp3, flac, mat"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'data-fallback="true"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'></section>'+'\n')
            file.write('\t'+'\t'+'\t'+'</div>'+'\n')
            file.write('\t'+'\t'+'</section>'+'\n')
            
            # Data Preview Images with unique IDs and error boundaries
            for z in range(len(MyDevices.dataProductFormatID[i])):
                file.write('\t'+'\t'+'<figure class="oncWidget data-preview-widget widget-isolated" id="dataPreview_'+str(widget_counter)+'_'+str(z)+'" data-widget="image" data-source="dataPreview"'+'\n')
                file.write('\t'+'\t'+'\t'+'data-widget-id="dataPreview_'+str(widget_counter)+'_'+str(z)+'"'+'\n')
                file.write('\t'+'\t'+'\t'+'url="https://data.oceannetworks.ca/DataPreviewService?operation=5&searchTreeNodeId='+str(MyDevices.searchTreeNodeID[i])+'&deviceCategoryId='+str(MyDevices.deviceCategoryID[i])+'&timeConfigId=2&dataProductFormatId='+str(MyDevices.dataProductFormatID[i][z])+'&plotNumber=1"'+'\n')
                file.write('\t'+'\t'+'\t'+'options="theme: gallery"'+'\n')
                file.write('\t'+'\t'+'\t'+'data-fallback="true"'+'\n')
                file.write('\t'+'\t'+'></figure>'+'\n')       
            file.write('\t'+'</div>'+'\n')
            
            widget_counter += 1
            
            # Widget Group 2: Archive Files with unique ID and error handling boundary
            file.write('\t'+'<div class="widget-container" id="widget_group_'+str(widget_counter)+'">'+'\n')
            file.write('\t'+'\t'+'<section class="oncWidgetGroup archive-files-group" source="plottingUtility" engine="name: dygraphs">'+'\n')
            file.write('\t'+'\t'+'\t'+'<div class="widgetWrap wgSensor">'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'<div class="device"><span>'+str(MyDevices.deviceID[i])+'</span>'+MyDevices.deviceName[i]+'</div>'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'<div class="clear"></div>'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'<section class="oncWidget widget-isolated" id="archiveFiles_'+str(widget_counter)+'" '+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'data-widget="archiveFiles" '+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'data-widget-id="archiveFiles_'+str(widget_counter)+'" '+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'dateFrom="yesterday" '+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'dateTo="yesterday+1h" '+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'extension="flac" '+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'deviceCode="'+str(MyDevices.deviceCode[i])+'" '+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'\t'+'data-fallback="true"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'></section>'+'\n') 
            file.write('\t'+'\t'+'\t'+'</div>'+'\n')
            file.write('\t'+'\t'+'</section>'+'\n')
            file.write('\t'+'</div>'+'\n')
            
            file.write('\t'+'</div>'+'\n')  # Close section
            
            widget_counter += 1
            section_counter += 1
    file.write('\t'+'</div>'+'\n')
    file.write('</body>'+'\n')   
    file.write('</html>'+'\n')  
    file.close                
    	    
print("Enhanced HTML dashboard generated successfully!")
hydrophone_word = 'hydrophone' if len(MyDevices) == 1 else 'hydrophones'
print(f"Generated report for {len(MyDevices)} {hydrophone_word}")

# Print summary of issues
critical_count = sum(1 for i in range(len(MyDevices)) if MyDevices.data_status[i]['overall_status'] == 'critical')
warning_count = sum(1 for i in range(len(MyDevices)) if MyDevices.data_status[i]['overall_status'] == 'warning')
minor_count = sum(1 for i in range(len(MyDevices)) if MyDevices.data_status[i]['overall_status'] == 'minor')
diverted_count = sum(1 for i in range(len(MyDevices)) if MyDevices.data_status[i]['overall_status'] == 'diverted')
good_count = len(MyDevices) - critical_count - warning_count - minor_count - diverted_count

print(f"\nSUMMARY:")
critical_issues_word = 'issue' if critical_count == 1 else 'issues'
print(f"Critical {critical_issues_word} (no data 3+ days): {critical_count}")
warning_issues_word = 'issue' if warning_count == 1 else 'issues' 
print(f"Warning {warning_issues_word} (1-2 days or multiple missing types): {warning_count}")
minor_issues_word = 'issue' if minor_count == 1 else 'issues'
print(f"Minor {minor_issues_word} (some missing data types): {minor_count}")
print(f"Diverted (intentional data suspension): {diverted_count}")
print(f"Good status: {good_count}")

if divert_parser and diverted_count > 0:
    print(f"\nDIVERT DETAILS:")
    for i in range(len(MyDevices)):
        if MyDevices.data_status[i]['overall_status'] == 'diverted':
            location = MyDevices.locationCode[i]
            status = MyDevices.data_status[i]
            print(f"  {location}: Diverted since {status['divert_since']}")
            
# Print divert summary if available
if divert_parser:
    divert_summary = divert_parser.get_divert_summary()
    print(f"\nDIVERT MONITORING SUMMARY:")
    print(f"Total divert events processed: {divert_summary['events_processed']}")
    print(f"Locations with divert status: {divert_summary['total_monitored']}")
    print(f"Currently diverted: {divert_summary['currently_diverted']}")
    print(f"Currently bypass: {divert_summary['currently_bypass']}")
