# Quick Start: Google Sheets API Setup

## ✅ Your Approach is Correct!

Your outlined steps are exactly right. Here's the detailed flow:

## Detailed Flow

### 1. **Enable Google Sheets API**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create/select a project
   - Navigate to **APIs & Services** > **Library**
   - Search "Google Sheets API" → Click **Enable**

### 2. **Configure OAuth Consent Screen**
   - Go to **APIs & Services** > **OAuth consent screen**
   - Choose **External** (unless you have Google Workspace)
   - Fill in app name, support email, developer email
   - **Add Scopes:**
     - `https://www.googleapis.com/auth/spreadsheets`
   - Add test users (if in testing mode)
   - Save

### 3. **Create OAuth 2.0 Credentials**
   - Go to **APIs & Services** > **Credentials**
   - Click **Create Credentials** > **OAuth client ID**
   - Application type: **Desktop app**
   - Name: "NCSAA Scheduler" (or any name)
   - **Save Client ID and Client Secret** (you'll need these)

### 4. **Download Credentials**
   - Click the download icon (⬇️) next to your OAuth client
   - Save the JSON file as `credentials.json` in the project root
   - This file contains your Client ID and Secret

### 5. **Get Access & Refresh Tokens**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Run authentication script
   python scripts/google_auth.py
   ```
   - This will open a browser for authorization
   - Grant permissions
   - Tokens will be saved to `token.json`

## Files Created

After setup, you'll have:
- `credentials.json` - OAuth client credentials (Client ID + Secret)
- `token.json` - Access token + Refresh token (auto-generated)

## Usage

```python
from app.services.google_sheets import GoogleSheetsService

service = GoogleSheetsService()

# Read data
data = service.read_range('SPREADSHEET_ID', 'Sheet1!A1:D10')

# Write data
service.write_range('SPREADSHEET_ID', 'Sheet1!A1', [['Data']])
```

## Important Notes

- ✅ `credentials.json` and `token.json` are in `.gitignore` (won't be committed)
- ✅ Access tokens expire after 1 hour (auto-refreshed)
- ✅ Refresh tokens don't expire (unless revoked)
- ✅ Never share or commit these files

## Need Help?

See `GOOGLE_SHEETS_SETUP.md` for detailed troubleshooting and advanced configuration.

