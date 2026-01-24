# Sheets Engine

The **Sheets Engine** is the core scheduling logic module for the NCSAA Basketball Scheduling System. It handles all data loading from Google Sheets, schedule generation, validation, and writing results back to Sheets.

## Architecture

This module contains all the business logic for:
- Reading data from Google Sheets
- Generating optimized game schedules
- Validating schedules against constraints
- Writing schedules back to Google Sheets

## Module Structure

### Core Files

- **`models.py`** - Data models (Team, School, Facility, Game, Schedule, etc.)
- **`config.py`** - Configuration constants and scheduling rules
- **`sheets_reader.py`** - Loads data from Google Sheets
- **`sheets_writer.py`** - Writes schedules back to Google Sheets
- **`scheduler.py`** - Schedule optimization engine using OR-Tools CP-SAT solver
- **`validator.py`** - Schedule validation against hard and soft constraints

### Data Flow

```
┌──────────────────┐
│  Google Sheets   │
│  (Input Data)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ sheets_reader.py │ ─── Loads: teams, facilities, rules
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  scheduler.py    │ ─── Generates optimized schedule
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  validator.py    │ ─── Validates constraints
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ sheets_writer.py │ ─── Writes schedule back
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Google Sheets   │
│  (Output)        │
└──────────────────┘
```

## Usage

### As a Module

```python
from sheets_engine import SheetsReader, ScheduleOptimizer, ScheduleValidator, SheetsWriter

# Load data
reader = SheetsReader()
teams, facilities, rules = reader.load_all_data()

# Generate schedule
optimizer = ScheduleOptimizer(teams, facilities, rules)
schedule = optimizer.optimize_schedule()

# Validate
validator = ScheduleValidator()
validation_result = validator.validate_schedule(schedule)

# Write back to Sheets
writer = SheetsWriter()
writer.write_schedule(schedule)
writer.write_summary_sheet(schedule, validation_result)
writer.write_team_schedules(schedule)
```

### Via API (Backend Engine)

The scheduling engine is exposed via the FastAPI backend in `api.py`:

```python
from sheets_engine.sheets_reader import SheetsReader
from sheets_engine.scheduler import ScheduleOptimizer
# ... etc
```

### Via CLI

The scheduling engine can be run directly from the command line using `main.py`:

```bash
python main.py
```

## Key Features

### Schedule Optimization
- Uses Google OR-Tools CP-SAT constraint programming solver
- Optimizes for:
  - 8 games per team (required)
  - Tier matching (same competitive level)
  - Geographic clustering
  - Home/away balance
  - Rival matchups
  - Facility availability

### Constraint Validation
- **Hard Constraints** (must be satisfied):
  - No time slot conflicts
  - Max 2 games per 7 days
  - Max 3 games per 14 days
  - Max 1 doubleheader per season
  - Respect "do not play" relationships
  - Facility availability

- **Soft Constraints** (preferences):
  - Home/away balance
  - Rival matchups scheduled
  - Tier matching
  - Geographic clustering

## Dependencies

- `gspread` - Google Sheets API
- `google-auth` - Google authentication
- `ortools` - Constraint programming solver
- Python 3.8+

## Configuration

All configurable settings are in `config.py`:
- Season dates
- Game duration and time slots
- Facility rules
- Scheduling priorities and weights
- Optimization parameters
