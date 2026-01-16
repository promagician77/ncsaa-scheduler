# NCSAA Scheduler

A Python application for scheduling.

## Project Structure

```
ncsaa-scheduler/
├── app/
│   ├── __init__.py
│   ├── config/          # Configuration settings
│   ├── models/          # Data models
│   ├── rules/           # Business rules and validation
│   ├── scheduler/       # Core scheduler functionality
│   ├── services/        # Service layer
│   └── utils/           # Utility functions
├── scripts/             # Utility scripts
├── tests/               # Test files
├── main.py              # Application entry point
├── requirements.txt     # Python dependencies
└── pyproject.toml       # Project configuration
```

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Development

Run the application:
```bash
python main.py
```

## Testing

Run tests:
```bash
pytest
```

## Google Sheets API Integration

This project includes Google Sheets API integration for reading and writing spreadsheet data.

### Quick Setup

1. **Enable Google Sheets API** in [Google Cloud Console](https://console.cloud.google.com/)
2. **Create OAuth 2.0 credentials** (Desktop app type)
3. **Download credentials** and save as `credentials.json` in project root
4. **Run authentication script:**
   ```bash
   python scripts/google_auth.py
   ```

For detailed instructions, see:
- **Quick Start:** [QUICK_START.md](QUICK_START.md)
- **Full Guide:** [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)

### Usage Example

```python
from app.services.google_sheets import GoogleSheetsService

service = GoogleSheetsService()
data = service.read_range('SPREADSHEET_ID', 'Sheet1!A1:D10')
```

See `scripts/example_usage.py` for more examples.

