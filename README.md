# Hydrophone Dashboard

Ocean Networks Canada (ONC) hydrophone data availability monitor with intelligent divert detection. Distinguishes between actual system issues and intentional diversions using percentage-based coverage analysis.

## Features

- **Percentage-Based Coverage Analysis**: Accurately measures data availability using file count thresholds rather than binary presence/absence
- **Historical Divert Integration**: Automatically explains missing data when aligned with diversion periods
- **Smart Status Classification**:
  - 🔄 **Diverted**: Intentionally suspended for diversion purposes
  - ✓ **Good**: Adequate data coverage (including divert-explained gaps)
  - ⚠ **Minor/Warning**: Partial coverage issues or unexplained gaps
  - ✗ **Critical**: Significant data outages requiring attention
- **Interactive Dashboard**: Web interface with detailed coverage statistics and divert history
- **Organized Package Structure**: Clean, maintainable codebase with separated concerns

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file:

```bash
# Required
ONC_TOKEN=your_onc_token_here

# Database (optional - uses fallbacks if unavailable)
DB_HOST=your_database_host
DB_NAME=your_database_name  
DB_USER=your_database_user
DB_PASSWORD=your_database_password

# Optional Configuration
DAYS_TO_FETCH=30
CHECK_LAST_N_DAYS=7

# Gmail Divert Monitoring (optional)
ENABLE_DIVERT_MONITORING=true
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
DIVERT_CHECK_DAYS=7
```

**Important:** Never commit the `.env` file to version control. It contains sensitive credentials.

**Getting Your ONC Token:**
1. Visit [Ocean Networks Canada Data Portal](https://data.oceannetworks.ca/)
2. Create an account or log in
3. Go to your profile/account settings
4. Generate or copy your API token

### 3. Run Dashboard

```bash
python Hydrophone.py
```

Generates `Hydrophone.html` with interactive monitoring dashboard.

## Gmail Divert Monitoring Setup (Optional)

The system can monitor Gmail emails to detect when hydrophones are intentionally diverted. This helps distinguish between actual data issues and expected diversions.

### 1. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API" and enable it
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client ID"
   - **Important**: When asked "What data will you be accessing?", select **"User data"** (not "Application data")
   - Configure the OAuth consent screen if prompted:
     - Set to "External" for testing
     - Add basic app information (name, your email)
   - Choose "Desktop Application" as the application type
   - Name it (e.g., "Hydrophone Divert Monitor")
   - Download the credentials JSON file

### 2. Configure Gmail Access

1. Save the downloaded credentials file as `credentials.json` in your project directory
2. Ensure your `.env` file includes the Gmail settings (see configuration above)
3. The Gmail account you use must have access to the divert notification emails

### 3. First-Time Authentication

On first run, the system will:
1. Open a web browser for Google OAuth consent
2. Ask you to grant permission to read Gmail emails
3. Save the access token for future use (in `token.json`)

### Location Mapping
The system includes pre-configured mappings for major hydrophone sites. To add custom mappings, edit `src/hydrophonedashboard/config/location_mappings.py`:

```python
LOCATION_MAPPING = {
    'SoG_East': ['ECHO3.H1', 'ECHO3.H2', 'ECHO3.H3', 'ECHO3.H4'],
    'ODP 1027': ['CBCH.H1', 'CBCH.H2', 'CBCH.H3', 'CBCH.H4'],
    # Add your specific email→hydrophone mappings
}
```

## Project Structure

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for detailed project organization and module descriptions.

## Testing

```bash
# Test location mappings and divert integration
python scripts/test_mappings.py

# Discover available hydrophone locations
python scripts/list_locations.py
```

## Configuration Options

- `CHECK_LAST_N_DAYS`: Analysis period for coverage assessment (default: 7)
- `DAYS_TO_FETCH`: Historical data range for dashboard plots (default: 30)
- `DIVERT_CHECK_DAYS`: Email search period for divert detection (default: 7)
- `ENABLE_DIVERT_MONITORING`: Enable Gmail divert integration (default: true)

## How It Works

1. **Coverage Analysis**: Counts actual files per day vs expected, calculates coverage percentages
2. **Threshold Detection**: Uses 30% coverage threshold to identify poor vs adequate data days  
3. **Divert Alignment**: Compares missing data periods with historical diversion windows
4. **Smart Status**: Assigns status based on coverage deficits and divert explanations

This approach accurately distinguishes between system failures and expected diversions, reducing false alarms and improving monitoring actionability.

## Troubleshooting

### Gmail Integration Issues

**"Gmail credentials not found"**
- Ensure you've downloaded the credentials file from Google Cloud Console
- Save it as `credentials.json` in the project directory
- Check the `GMAIL_CREDENTIALS_PATH` setting in your `.env` file

**"Gmail authentication failed"**
- Delete the `token.json` file and re-run the application
- This will trigger a new OAuth consent flow
- Ensure the Gmail account has access to divert emails

**"No divert emails found"**
- This is normal if no recent divert events occurred
- Check that the Gmail account receives divert notification emails

### Other Issues

**Location Mapping**: Update mappings in `src/hydrophonedashboard/config/location_mappings.py` to match your email location names

**Database Issues**: Application continues with reduced functionality if database unavailable

**Coverage Analysis**: Check console output for per-day coverage percentages and expected file counts 