"""
Google Sheets API Service

This service handles all interactions with Google Sheets API,
including authentication, reading, and writing data.
"""

import os
import json
from typing import List, Any, Optional
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleSheetsService:
    """Service for interacting with Google Sheets API."""

    # Scopes required for Google Sheets access
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize the Google Sheets service.

        Args:
            credentials_path: Path to credentials.json file.
                            Defaults to 'credentials.json' in project root.
        """
        self.credentials_path = credentials_path or self._get_default_credentials_path()
        self.token_path = self._get_token_path()
        self.creds = None
        self.service = None
        self._authenticate()

    def _get_default_credentials_path(self) -> str:
        """Get the default path for credentials.json."""
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / 'credentials.json')

    def _get_token_path(self) -> str:
        """Get the path for storing tokens."""
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / 'token.json')

    def _authenticate(self) -> None:
        """
        Authenticate and create the Google Sheets service.

        This method handles:
        1. Loading existing credentials from token.json
        2. Refreshing expired tokens
        3. Running OAuth flow if no credentials exist
        """
        # Load existing credentials
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(
                self.token_path, self.SCOPES
            )

        # If there are no (valid) credentials available, let the user log in
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                # Refresh expired token
                self.creds.refresh(Request())
            else:
                # Run OAuth flow
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Credentials file not found at {self.credentials_path}. "
                        "Please run the authentication script first: "
                        "python scripts/google_auth.py"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())

        # Build the service
        self.service = build('sheets', 'v4', credentials=self.creds)

    def read_range(
        self,
        spreadsheet_id: str,
        range_name: str,
        value_render_option: str = 'FORMATTED_VALUE'
    ) -> List[List[Any]]:
        """
        Read data from a Google Sheet.

        Args:
            spreadsheet_id: The ID of the spreadsheet (from the URL)
            range_name: A1 notation range (e.g., 'Sheet1!A1:D10')
            value_render_option: How values should be rendered
                                ('FORMATTED_VALUE', 'UNFORMATTED_VALUE', 'FORMULA')

        Returns:
            List of rows, where each row is a list of cell values

        Raises:
            HttpError: If the API request fails
        """
        try:
            sheet = self.service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueRenderOption=value_render_option
            ).execute()
            values = result.get('values', [])
            return values
        except HttpError as error:
            raise Exception(f"An error occurred while reading: {error}")

    def write_range(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
        value_input_option: str = 'RAW'
    ) -> dict:
        """
        Write data to a Google Sheet.

        Args:
            spreadsheet_id: The ID of the spreadsheet (from the URL)
            range_name: A1 notation range (e.g., 'Sheet1!A1')
            values: List of rows, where each row is a list of cell values
            value_input_option: How input data should be interpreted
                               ('RAW', 'USER_ENTERED')

        Returns:
            Dictionary with update result information

        Raises:
            HttpError: If the API request fails
        """
        try:
            body = {
                'values': values
            }
            sheet = self.service.spreadsheets()
            result = sheet.values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body
            ).execute()
            return result
        except HttpError as error:
            raise Exception(f"An error occurred while writing: {error}")

    def append_range(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
        value_input_option: str = 'RAW',
        insert_data_option: str = 'INSERT_ROWS'
    ) -> dict:
        """
        Append data to a Google Sheet.

        Args:
            spreadsheet_id: The ID of the spreadsheet (from the URL)
            range_name: A1 notation range (e.g., 'Sheet1!A1')
            values: List of rows to append
            value_input_option: How input data should be interpreted
            insert_data_option: How to insert data ('INSERT_ROWS', 'OVERWRITE')

        Returns:
            Dictionary with append result information

        Raises:
            HttpError: If the API request fails
        """
        try:
            body = {
                'values': values
            }
            sheet = self.service.spreadsheets()
            result = sheet.values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                insertDataOption=insert_data_option,
                body=body
            ).execute()
            return result
        except HttpError as error:
            raise Exception(f"An error occurred while appending: {error}")

    def clear_range(
        self,
        spreadsheet_id: str,
        range_name: str
    ) -> dict:
        """
        Clear data from a Google Sheet range.

        Args:
            spreadsheet_id: The ID of the spreadsheet
            range_name: A1 notation range to clear

        Returns:
            Dictionary with clear result information

        Raises:
            HttpError: If the API request fails
        """
        try:
            sheet = self.service.spreadsheets()
            result = sheet.values().clear(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            return result
        except HttpError as error:
            raise Exception(f"An error occurred while clearing: {error}")

    def get_spreadsheet_info(self, spreadsheet_id: str) -> dict:
        """
        Get metadata about a spreadsheet.

        Args:
            spreadsheet_id: The ID of the spreadsheet

        Returns:
            Dictionary with spreadsheet metadata

        Raises:
            HttpError: If the API request fails
        """
        try:
            sheet = self.service.spreadsheets()
            result = sheet.get(spreadsheetId=spreadsheet_id).execute()
            return result
        except HttpError as error:
            raise Exception(f"An error occurred while getting info: {error}")

