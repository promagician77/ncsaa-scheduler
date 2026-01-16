# Google Sheets API Connection Flow

## ✅ Your Approach is 100% Correct!

Here's the detailed flow that matches your outlined steps:

## Step-by-Step Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Google Developer Console                            │
│ ─────────────────────────────────────────────────────────── │
│ • Go to console.cloud.google.com                            │
│ • Create/Select Project                                      │
│ • Enable Google Sheets API                                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Create OAuth App                                    │
│ ─────────────────────────────────────────────────────────── │
│ • Configure OAuth Consent Screen                            │
│   - App name, emails                                        │
│   - Add scopes (Google Sheets)                              │
│ • Create OAuth 2.0 Client ID                                │
│   - Type: Desktop app                                       │
│   - Get Client ID & Secret                                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Define Scope with Google Sheets Enabled             │
│ ─────────────────────────────────────────────────────────── │
│ Scope: https://www.googleapis.com/auth/spreadsheets        │
│ (This is done in OAuth Consent Screen configuration)        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Get Google ID and Secret Key                       │
│ ─────────────────────────────────────────────────────────── │
│ • Download credentials.json from Google Cloud Console       │
│ • Contains:                                                 │
│   - client_id (Google ID)                                   │
│   - client_secret (Secret Key)                              │
│ • Save as credentials.json in project root                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 5: Get Access Token and Refresh Token                  │
│ ─────────────────────────────────────────────────────────── │
│ • Run: python scripts/google_auth.py                        │
│ • Browser opens for authorization                           │
│ • User grants permissions                                   │
│ • Tokens saved to token.json:                               │
│   - access_token (expires in 1 hour)                        │
│   - refresh_token (long-lived)                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Ready to Use!                                               │
│ ─────────────────────────────────────────────────────────── │
│ • Access token used for API calls                           │
│ • Auto-refreshed when expired                               │
│ • Use GoogleSheetsService to read/write data                │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Implementation Steps

### 1. Enable Google Sheets API
- **Location:** Google Cloud Console → APIs & Services → Library
- **Action:** Search "Google Sheets API" → Click Enable
- **Result:** API is enabled for your project

### 2. Create OAuth App
- **Location:** APIs & Services → OAuth consent screen
- **Steps:**
  - Choose "External" user type
  - Fill app information
  - Add scopes: `https://www.googleapis.com/auth/spreadsheets`
  - Add test users (if in testing mode)
  - Save

### 3. Define Scope
- **Scope:** `https://www.googleapis.com/auth/spreadsheets`
- **Permission:** Full read/write access to Google Sheets
- **Where:** Added in OAuth consent screen (Step 2)

### 4. Get Client ID and Secret
- **Location:** APIs & Services → Credentials
- **Action:** Create Credentials → OAuth client ID
- **Type:** Desktop app
- **Result:** 
  - Client ID (visible)
  - Client Secret (visible once, save it!)
  - Download JSON file → Save as `credentials.json`

### 5. Get Access & Refresh Tokens
- **Method:** Run authentication script
- **Command:** `python scripts/google_auth.py`
- **Process:**
  1. Script reads `credentials.json`
  2. Opens browser for OAuth flow
  3. User authorizes application
  4. Google returns authorization code
  5. Script exchanges code for tokens
  6. Tokens saved to `token.json`
- **Result:**
  - `access_token`: Used for API calls (expires in 1 hour)
  - `refresh_token`: Used to get new access tokens (long-lived)

## Token Lifecycle

```
┌──────────────┐
│ Access Token │  (Expires in 1 hour)
└──────┬───────┘
       │
       │ When expired
       ↓
┌──────────────┐      ┌──────────────┐
│Refresh Token │ ────→│ New Access   │
│(Long-lived)  │      │ Token        │
└──────────────┘      └──────────────┘
```

The `GoogleSheetsService` automatically handles token refresh.

## Files Overview

| File | Purpose | Contains |
|------|---------|----------|
| `credentials.json` | OAuth client config | Client ID, Client Secret |
| `token.json` | User tokens | Access Token, Refresh Token |
| `app/services/google_sheets.py` | Service class | API interaction logic |
| `scripts/google_auth.py` | Auth script | OAuth flow automation |

## Security Checklist

- ✅ `credentials.json` in `.gitignore`
- ✅ `token.json` in `.gitignore`
- ✅ Never commit credentials
- ✅ Use environment variables for production
- ✅ Rotate credentials if compromised

## Next Steps

1. Follow the steps above
2. Run `python scripts/google_auth.py`
3. Start using `GoogleSheetsService` in your code
4. See `scripts/example_usage.py` for examples

---

**Your approach is perfect!** This flow matches exactly what you outlined. The implementation is ready to use.

