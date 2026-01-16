# Google Sheets API Integration Guide

## Overview
This guide provides step-by-step instructions for connecting to the Google Sheets API using OAuth 2.0.

## Step-by-Step Setup

### Step 1: Enable Google Sheets API in Google Developer Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** > **Library**
4. Search for "Google Sheets API"
5. Click on it and press **Enable**

### Step 2: Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. If prompted, configure the OAuth consent screen first:
   - Choose **External** (unless you have a Google Workspace account)
   - Fill in the required information:
     - App name
     - User support email
     - Developer contact email
   - Add scopes (see Step 3)
   - Add test users (if in testing mode)
   - Save and continue through the steps

### Step 3: Define OAuth Scopes

When configuring the OAuth consent screen, add these scopes:
- `https://www.googleapis.com/auth/spreadsheets` (Full access to Google Sheets)
- `https://www.googleapis.com/auth/drive.readonly` (Optional: Read-only access to Google Drive)

**Common Scopes:**
- `https://www.googleapis.com/auth/spreadsheets` - Full read/write access to spreadsheets
- `https://www.googleapis.com/auth/spreadsheets.readonly` - Read-only access
- `https://www.googleapis.com/auth/drive` - Full access to Google Drive
- `https://www.googleapis.com/auth/drive.readonly` - Read-only access to Google Drive

### Step 4: Create OAuth Client ID

1. After configuring the consent screen, go back to **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Choose application type:
   - **Desktop app** (for command-line applications)
   - **Web application** (for web apps)
4. Give it a name (e.g., "NCSAA Scheduler")
5. For Desktop apps, you can leave redirect URIs empty or add:
   - `http://localhost:8080/` (for local development)
   - `urn:ietf:wg:oauth:2.0:oob` (for installed apps)
6. Click **Create**
7. **Save the Client ID and Client Secret** - you'll need these!

### Step 5: Get Access Token and Refresh Token

#### Option A: Using the Python Script (Recommended)
Run the provided authentication script:
```bash
python scripts/google_auth.py
```

This will:
1. Open a browser for authentication
2. Ask you to authorize the application
3. Save the credentials to `credentials.json`
4. Store tokens for future use

#### Option B: Manual Flow
1. Use the OAuth 2.0 Playground or a tool to get the authorization code
2. Exchange the authorization code for access and refresh tokens
3. Store the refresh token securely (it's used to get new access tokens)

## Configuration

### Environment Variables
Create a `.env` file in the project root:
```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8080/
```

### Credentials File
After authentication, you'll have:
- `credentials.json` - Contains access token, refresh token, and client credentials
- This file should be in `.gitignore` (already included)

## Usage

Once set up, you can use the Google Sheets service:

```python
from app.services.google_sheets import GoogleSheetsService

service = GoogleSheetsService()
# Read from a sheet
data = service.read_range('SPREADSHEET_ID', 'Sheet1!A1:D10')
# Write to a sheet
service.write_range('SPREADSHEET_ID', 'Sheet1!A1', [['Data', 'Here']])
```

## Security Notes

1. **Never commit credentials to version control**
2. Store credentials securely (use environment variables or secure vaults)
3. Refresh tokens don't expire (unless revoked), so keep them secure
4. Access tokens expire after 1 hour - the service automatically refreshes them
5. For production, consider using service accounts instead of OAuth for server-to-server communication

## Troubleshooting

### Common Issues

1. **"Access blocked: This app's request is invalid"**
   - Make sure you've added test users in the OAuth consent screen (if in testing mode)
   - Verify redirect URIs match exactly

2. **"Invalid credentials"**
   - Check that Client ID and Secret are correct
   - Ensure credentials.json exists and is valid

3. **"Token expired"**
   - The service should auto-refresh, but if not, re-run the auth script

4. **"Insufficient permissions"**
   - Verify the correct scopes are requested
   - Check that the user has granted all necessary permissions

