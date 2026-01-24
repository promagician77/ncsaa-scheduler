# Migration Guide: Old Structure to New Structure

## Overview

The backend has been restructured into a proper Python package with organized directories.

## Old Structure (Deprecated)

```
backend/
├── api.py
├── config.py
├── models.py
├── scheduler.py
├── validator.py
├── sheets_reader.py
├── sheets_writer.py
├── main.py
├── run_api.py
└── test_*.py
```

## New Structure (Current)

```
backend/
├── app/
│   ├── main.py          # FastAPI app (replaces api.py)
│   ├── api/routes.py    # API endpoints
│   ├── core/config.py   # Configuration
│   ├── models/models.py # Data models
│   └── services/        # Business logic
├── scripts/
│   ├── run_api.py       # API server runner
│   └── run_scheduler.py # CLI scheduler (replaces main.py)
└── tests/               # All test files
```

## Import Changes

### Old Imports
```python
from models import Team, Facility
from scheduler import ScheduleOptimizer
from config import SPREADSHEET_ID
```

### New Imports
```python
from app.models import Team, Facility
from app.services.scheduler import ScheduleOptimizer
from app.core.config import SPREADSHEET_ID
```

## Running the Application

### Old Way
```bash
python run_api.py
python main.py
```

### New Way
```bash
python scripts/run_api.py
python scripts/run_scheduler.py
```

## Backward Compatibility

The old files in the root `backend/` directory are kept for backward compatibility but are deprecated. Please migrate to the new structure.
