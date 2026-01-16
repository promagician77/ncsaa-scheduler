"""
Example usage of Google Sheets Service

This script demonstrates how to use the GoogleSheetsService
to read and write data to Google Sheets.
"""

from app.services.google_sheets import GoogleSheetsService


def example_read():
    """Example: Read data from a Google Sheet."""
    # Initialize the service
    service = GoogleSheetsService()

    # Replace with your spreadsheet ID (from the URL)
    # Example URL: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
    spreadsheet_id = 'YOUR_SPREADSHEET_ID_HERE'

    # Read a range of cells
    range_name = 'Sheet1!A1:D10'
    values = service.read_range(spreadsheet_id, range_name)

    print("Read values:")
    for row in values:
        print(row)


def example_write():
    """Example: Write data to a Google Sheet."""
    # Initialize the service
    service = GoogleSheetsService()

    # Replace with your spreadsheet ID
    spreadsheet_id = 'YOUR_SPREADSHEET_ID_HERE'

    # Prepare data to write (list of rows)
    values = [
        ['Name', 'Age', 'City'],
        ['John Doe', 30, 'New York'],
        ['Jane Smith', 25, 'Los Angeles'],
        ['Bob Johnson', 35, 'Chicago']
    ]

    # Write to the sheet (starting at A1)
    result = service.write_range(spreadsheet_id, 'Sheet1!A1', values)
    print(f"Updated {result.get('updatedCells')} cells")


def example_append():
    """Example: Append data to a Google Sheet."""
    # Initialize the service
    service = GoogleSheetsService()

    # Replace with your spreadsheet ID
    spreadsheet_id = 'YOUR_SPREADSHEET_ID_HERE'

    # Data to append
    new_rows = [
        ['Alice Brown', 28, 'Seattle'],
        ['Charlie Wilson', 32, 'Boston']
    ]

    # Append to the sheet
    result = service.append_range(spreadsheet_id, 'Sheet1!A1', new_rows)
    print(f"Appended {result.get('updates', {}).get('updatedCells')} cells")


def example_get_info():
    """Example: Get spreadsheet metadata."""
    # Initialize the service
    service = GoogleSheetsService()

    # Replace with your spreadsheet ID
    spreadsheet_id = 'YOUR_SPREADSHEET_ID_HERE'

    # Get spreadsheet information
    info = service.get_spreadsheet_info(spreadsheet_id)
    print(f"Spreadsheet title: {info.get('properties', {}).get('title')}")
    print(f"Sheets: {[s['properties']['title'] for s in info.get('sheets', [])]}")


if __name__ == '__main__':
    print("Google Sheets API Example Usage")
    print("=" * 50)
    print("\n⚠️  Make sure to:")
    print("1. Run 'python scripts/google_auth.py' first to authenticate")
    print("2. Replace 'YOUR_SPREADSHEET_ID_HERE' with your actual spreadsheet ID")
    print("3. Uncomment the example function you want to run")
    print()

    # Uncomment the example you want to run:
    # example_read()
    # example_write()
    # example_append()
    # example_get_info()

