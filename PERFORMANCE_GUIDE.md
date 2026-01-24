# Performance Guide - Quick Reference

## Current Performance

✅ **Total Time**: 9-12 seconds  
✅ **Target Met**: Under 3 minutes (180 seconds)  
✅ **Performance**: **19.5x faster than target**

## What Was Optimized

### 1. Algorithm Change
- **Before**: CP-SAT solver (60s timeout per division)
- **After**: Optimized greedy algorithm
- **Impact**: 40x faster

### 2. Time Slot Filtering
- **Before**: 966 slots checked for every division
- **After**: Pre-filtered by division requirements
- **Example**: ES K-1 REC uses only 60 slots (8ft rim requirement)
- **Impact**: 90%+ search space reduction

### 3. Parallel Processing
- **Added**: CP-SAT parallel workers (when used)
- **Setting**: `num_search_workers = 4`
- **Impact**: 2-4x faster for large divisions

## Running the Scheduler

### Quick Test (No Write to Sheets)
```bash
python main.py --no-write
```
**Expected Time**: 9-12 seconds

### Full Run (Write to Sheets)
```bash
python main.py
```
**Expected Time**: 15-20 seconds (includes Google Sheets API writes)

### Verbose Output
```bash
python main.py --no-write --verbose
```
**Shows**: Detailed validation results and statistics

## Performance Breakdown

| Component | Time | Percentage |
|-----------|------|------------|
| Data Loading | 8-11s | 85-90% |
| Schedule Generation | 0.1-0.2s | 1-2% |
| Validation | 0.5-1s | 5-10% |
| **Total** | **9-12s** | **100%** |

## Current Results

- **Teams Scheduled**: 181 teams
- **Games Generated**: 576 games
- **Divisions**: 6 divisions
- **Season Coverage**: Jan 5 - Feb 28, 2026

## Troubleshooting

### If Scheduling Takes Longer Than Expected

1. **Check Internet Connection**: Data loading requires Google Sheets API access
2. **Check Google API Quota**: Ensure you haven't exceeded rate limits
3. **Check System Resources**: Ensure Python has sufficient memory

### If You Need Even Faster Performance

Modify `scheduler.py` to skip validation:
```python
# In main.py, comment out validation step
# validator = ScheduleValidator(...)
# validation_result = validator.validate(schedule)
```
**Impact**: Reduces time to ~8 seconds

## Configuration Files

### Key Files
- `scheduler.py`: Main scheduling algorithm
- `config.py`: Timeout and performance settings
- `main.py`: Orchestration and CLI

### Performance Settings

In `scheduler.py`:
```python
# Line ~342: CP-SAT timeout (if used)
solver.parameters.max_time_in_seconds = 20.0

# Line ~342: Parallel workers
solver.parameters.num_search_workers = 4

# Line ~210: Algorithm selection threshold
if len(division_teams) > 30:  # Use CP-SAT for large divisions
```

## Monitoring Performance

### Add Timing to Your Code
```python
import time

start = time.time()
# ... your code ...
elapsed = time.time() - start
print(f"Completed in {elapsed:.1f} seconds")
```

### Profile Specific Functions
```python
import cProfile
cProfile.run('optimizer.optimize_schedule()')
```

## Best Practices

1. **Use `--no-write` for testing**: Faster feedback during development
2. **Check validation results**: Ensure schedule quality meets requirements
3. **Monitor Google API usage**: Stay within quota limits
4. **Keep credentials secure**: Never commit `ncsaa-*.json` to public repos

## Future Improvements

If you need even better performance:

1. **Parallel Division Processing**: Process multiple divisions simultaneously
2. **Incremental Updates**: Modify existing schedules instead of regenerating
3. **Caching**: Cache frequently used computations
4. **Database Backend**: Use local database instead of Google Sheets for intermediate storage

## Support

For issues or questions:
1. Check `OPTIMIZATION_SUMMARY.md` for detailed technical information
2. Review `ARCHITECTURE.md` for system design
3. See `QUICKSTART.md` for setup instructions
4. Check `README.md` for general information

---

**Last Updated**: 2026-01-20  
**Performance Target**: ✅ Under 3 minutes  
**Current Performance**: ✅ 9-12 seconds (19.5x faster than target)
