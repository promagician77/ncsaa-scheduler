# Quick Start Guide

## Getting Started in 5 Minutes

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Verify Installation

```bash
python test_scheduler.py
```

You should see: "All tests passed!"

### 3. Run the Scheduler

**Windows:**
```bash
run_scheduler.bat
```

**Mac/Linux:**
```bash
chmod +x run_scheduler.sh
./run_scheduler.sh
```

**Or directly:**
```bash
python main.py
```

### 4. View Results

The scheduler will:
1. Read data from Google Sheets
2. Generate an optimized schedule
3. Validate the schedule
4. Write results back to Google Sheets

Check your Google Sheet for:
- **26 WINTER WEEK 1, 2, 3...** - Weekly schedules
- **SCHEDULE SUMMARY** - Statistics and validation
- **TEAM SCHEDULES** - Individual team schedules

## Command Line Options

```bash
# Generate schedule without writing to Google Sheets (dry run)
python main.py --no-write

# Enable verbose output
python main.py --verbose

# Combine options
python main.py --no-write --verbose
```

## What the System Does

### Input (from Google Sheets)
- Team information (school, division, coach)
- Facility information (location, availability, courts)
- Rules (season dates, holidays, constraints)
- Relationships (rivals, do-not-play)

### Processing
- Uses Google OR-Tools CP-SAT constraint solver
- Applies 10+ hard constraints (must satisfy)
- Optimizes 8+ soft constraints (preferences)
- Validates all schedules

### Output (to Google Sheets)
- Weekly game schedules
- Team-by-team schedules
- Summary statistics
- Validation report

## Understanding the Output

### Weekly Schedule Sheets
Each week has its own sheet showing:
- Date and time of each game
- Home and away teams
- Facility and court number
- Division

### Schedule Summary
Shows:
- Total games scheduled
- Games per division
- Games per week
- Team statistics
- Validation results

### Team Schedules
Individual schedule for each team:
- All games in chronological order
- Home/away designation
- Opponent information
- Facility details

## Troubleshooting

### "No teams loaded"
- Check that Google Sheet has data in "WINTER BASKETBALL TEAM LIST"
- Verify service account has access to the sheet

### "No solution found"
- Too many constraints - try relaxing some rules
- Not enough time slots - check season dates and facility availability
- Conflicting relationships - review do-not-play constraints

### "Hard constraint violations"
- The schedule was generated but has issues
- Review the validation report in output
- May need manual adjustments

### Google Sheets errors
- Verify `ncsaa-484512-3f8c48632375.json` exists
- Check SPREADSHEET_ID in `config.py`
- Ensure service account has edit permissions

## Customization

### Change Season Dates
Edit `config.py`:
```python
SEASON_START_DATE = "2026-01-05"
SEASON_END_DATE = "2026-02-28"
```

### Adjust Game Times
Edit `config.py`:
```python
WEEKNIGHT_START_TIME = time(17, 0)  # 5:00 PM
WEEKNIGHT_END_TIME = time(20, 30)   # 8:30 PM
```

### Modify Constraints
Edit `config.py`:
```python
MAX_GAMES_PER_7_DAYS = 2
MAX_GAMES_PER_14_DAYS = 3
```

### Change Priority Weights
Edit `config.py`:
```python
PRIORITY_WEIGHTS = {
    "tier_matching": 70,
    "geographic_cluster": 60,
    # ... etc
}
```

## Advanced Usage

### Generate Without Writing
Useful for testing changes:
```bash
python main.py --no-write
```

### Run Tests
Before making changes:
```bash
python test_scheduler.py
```

### Check Specific Files
```bash
python -c "from sheets_reader import SheetsReader; r = SheetsReader(); teams, facilities, rules = r.load_all_data()"
```

## Architecture

```
main.py                 → Orchestrates everything
├── sheets_reader.py    → Loads data from Google Sheets
├── scheduler.py        → Generates optimal schedule (CP-SAT solver)
├── validator.py        → Validates schedule against constraints
└── sheets_writer.py    → Writes results back to Google Sheets
```

## Support

For issues:
1. Check this guide
2. Review README.md
3. Run test_scheduler.py
4. Check error messages in output

## Next Steps

1. Review the generated schedule in Google Sheets
2. Check validation results in SCHEDULE SUMMARY
3. Make manual adjustments if needed
4. Share schedules with coaches

Enjoy your optimized basketball schedule! 🏀
