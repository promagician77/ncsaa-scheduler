# NCSAA Basketball Scheduling System - Backend

## Project Structure

```
backend/
├── app/                    # Main application package
│   ├── __init__.py
│   ├── main.py            # FastAPI application entry point
│   ├── api/               # API routes
│   │   ├── __init__.py
│   │   └── routes.py     # API endpoint definitions
│   ├── core/              # Core configuration
│   │   ├── __init__.py
│   │   └── config.py     # Configuration constants
│   ├── models/            # Data models
│   │   ├── __init__.py
│   │   └── models.py     # All data structures (Team, Facility, Game, etc.)
│   └── services/          # Business logic services
│       ├── __init__.py
│       ├── scheduler.py   # Schedule optimization logic
│       ├── validator.py  # Schedule validation
│       ├── sheets_reader.py  # Google Sheets data reader
│       └── sheets_writer.py  # Google Sheets data writer
├── tests/                 # Test suite
│   ├── __init__.py
│   ├── test_scheduler.py
│   ├── test_validator.py
│   ├── test_game_counts.py
│   ├── test_time_rules.py
│   └── test_time_slots_only.py
├── scripts/               # Utility scripts
│   ├── __init__.py
│   ├── run_scheduler.py  # CLI scheduler runner
│   └── run_api.py        # API server runner
├── requirements.txt       # Core dependencies
├── requirements-api.txt   # API-specific dependencies
├── .env.example           # Environment variables template
├── .env                   # Environment variables (create from .env.example)
└── credentials/           # Google Sheets credentials (gitignored)
    └── ncsaa-484512-3f8c48632375.json
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-api.txt
```

2. Set up Google Sheets credentials (choose one method):

   **Method 1: Environment Variable (Recommended)**
   
   Create a `.env` file in the `backend` directory:
   ```bash
   cp .env.example .env
   ```
   
   Then edit `.env` and add your credentials:
   ```bash
   # Option A: JSON string (most secure, no file needed)
   GOOGLE_SHEETS_CREDENTIALS_JSON='{"type":"service_account","project_id":"...","private_key":"...","client_email":"..."}'
   
   # Option B: File path
   GOOGLE_SHEETS_CREDENTIALS_FILE=/path/to/your/credentials.json
   ```
   
   **Method 2: Default File Location (Legacy)**
   
   Place your credentials JSON file as `ncsaa-484512-3f8c48632375.json` in the `backend/credentials/` directory.
   
   **Note:** The `.env` file is gitignored and will not be committed to version control.

## Running the Application

### Run the API Server

```bash
# From backend directory
python scripts/run_api.py

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/health

### Run the CLI Scheduler

```bash
# From backend directory
python scripts/run_scheduler.py

# Options:
python scripts/run_scheduler.py --no-write    # Generate without writing to Sheets
python scripts/run_scheduler.py --verbose     # Enable verbose output
```

## API Endpoints

- `POST /api/schedule` - Generate a new schedule
- `GET /api/stats` - Get schedule statistics
- `GET /api/health` - Health check

## Running Tests

```bash
# From backend directory
python tests/test_scheduler.py
python tests/test_game_counts.py
python tests/test_time_rules.py
python tests/test_time_slots_only.py
```

## Import Structure

All imports use the `app` package prefix:

```python
from app.models import Team, Facility, Game
from app.services.scheduler import ScheduleOptimizer
from app.services.validator import ScheduleValidator
from app.core.config import SPREADSHEET_ID, get_google_credentials
```

## Development Notes

- The `app/` directory contains all application code
- The `tests/` directory contains all test files
- The `scripts/` directory contains runnable scripts
- Configuration is centralized in `app/core/config.py`
- All data models are in `app/models/models.py`
- Business logic is in `app/services/`
