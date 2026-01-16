"""
Google OAuth Authentication Script

This script helps you authenticate with Google Sheets API and obtain
access and refresh tokens.

Run this script once to set up authentication:
    python scripts/google_auth.py
"""

import os
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes required for Google Sheets access
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def get_credentials_path() -> str:
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    return str(project_root / 'credentials.json')


def get_token_path() -> str:
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    return str(project_root / 'token.json')

def authenticate():
    creds = None
    credentials_path = get_credentials_path()
    token_path = get_token_path()

    if not os.path.exists(credentials_path):
        print(f"\n❌ Error: credentials.json not found at {credentials_path}")
        print("\n📋 Please follow these steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project or select an existing one")
        print("3. Enable Google Sheets API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print("5. Download the credentials JSON file")
        print(f"6. Save it as 'credentials.json' in the project root: {Path(credentials_path).parent}")
        print("\nFor detailed instructions, see GOOGLE_SHEETS_SETUP.md")
        return None

    # Load existing token if available
    if os.path.exists(token_path):
        print("📂 Loading existing token...")
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🔐 Starting OAuth flow...")
            print("📝 A browser window will open for authentication.")
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        print(f"💾 Saving token to {token_path}...")
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

        print("✅ Authentication successful!")
        print(f"📄 Token saved to: {token_path}")
        print("\n🎉 You can now use the Google Sheets service!")
    else:
        print("✅ Valid credentials found. No action needed.")

    return creds


def main():
    """Main function to run authentication."""
    print("=" * 60)
    print("Google Sheets API Authentication")
    print("=" * 60)
    print()

    try:
        creds = authenticate()
        if creds:
            print("\n✨ Setup complete! You can now use Google Sheets API.")
        else:
            print("\n❌ Authentication failed. Please check the error messages above.")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        print("\nPlease check:")
        print("1. credentials.json exists and is valid")
        print("2. You have internet connection")
        print("3. Google Sheets API is enabled in your project")
        print("\nFor help, see GOOGLE_SHEETS_SETUP.md")


if __name__ == '__main__':
    main()

