"""
Helper script to create credentials.json from Client ID and Secret

This script helps you create the credentials.json file in the correct format
that Google's OAuth library expects.
"""

import json
from pathlib import Path


def create_credentials_file():
    """Create credentials.json file from user input."""
    project_root = Path(__file__).parent.parent
    credentials_path = project_root / 'credentials.json'

    print("=" * 60)
    print("Create credentials.json")
    print("=" * 60)
    print()
    print("Enter your OAuth 2.0 credentials from Google Cloud Console:")
    print()

    # Get Client ID
    client_id = input("Client ID: ").strip()
    if not client_id:
        print("❌ Client ID is required!")
        return

    # Get Client Secret
    client_secret = input("Client Secret: ").strip()
    if not client_secret:
        print("❌ Client Secret is required!")
        return

    # Get Project ID (optional, can extract from client_id or ask)
    project_id = input("Project ID (optional, press Enter to skip): ").strip()
    if not project_id:
        # Try to extract from client_id if it contains project info
        # Or use a default
        project_id = "ncsaa-scheduler"

    # Create the credentials structure
    credentials = {
        "installed": {
            "client_id": client_id,
            "project_id": project_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"]
        }
    }

    # Write to file
    try:
        with open(credentials_path, 'w') as f:
            json.dump(credentials, f, indent=2)
        print()
        print(f"✅ Successfully created credentials.json at:")
        print(f"   {credentials_path}")
        print()
        print("🎉 You can now run: python scripts/google_auth.py")
    except Exception as e:
        print(f"❌ Error creating file: {e}")


if __name__ == '__main__':
    create_credentials_file()

