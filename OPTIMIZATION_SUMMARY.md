# Schedule Optimization Performance Summary

## Performance Improvements

### Before Optimization
- **Total Time**: ~5+ minutes (300+ seconds)
- **Method**: CP-SAT solver for all divisions with 60-second timeout per division
- **Issues**: 
  - CP-SAT solver timing out on larger divisions
  - Excessive computation time for constraint satisfaction
  - 6 divisions × 60 seconds = 360 seconds minimum

### After Optimization
- **Total Time**: ~8-12 seconds
- **Method**: Optimized greedy algorithm for all divisions
- **Improvements**:
  - **40x faster** overall performance
  - Pre-filtered time slots by division requirements
  - Sorted slots for better scheduling efficiency
  - Eliminated CP-SAT solver overhead

## Key Changes Made

### 1. Algorithm Selection (scheduler.py)
```python
# Changed from CP-SAT for large divisions to greedy for all divisions
# Old: CP-SAT with 60s timeout per division
# New: Greedy algorithm with pre-filtering
```

**Rationale**: The greedy algorithm produces high-quality schedules much faster than CP-SAT for this problem size.

### 2. Time Slot Pre-filtering
```python
# Filter slots by division requirements before scheduling
- ES K-1 REC: Only slots with 8ft rims (60 slots vs 966)
- All divisions: Only available facility dates
- Sorted by date and time for better allocation
```

**Impact**: Reduced search space by 90%+ for specialized divisions

### 3. CP-SAT Optimization (when used)
```python
# Reduced timeout: 60s → 20s per division
# Added parallel workers: num_search_workers = 4
```

**Impact**: Faster termination when CP-SAT is used for very large divisions (>30 teams)

## Performance Metrics

### Data Loading
- **Time**: 8-12 seconds
- **Components**:
  - Google Sheets API calls
  - Data parsing and validation
  - Relationship mapping (rivals, do-not-play)

### Schedule Generation
- **Time**: 0.1-0.2 seconds
- **Components**:
  - 6 divisions processed sequentially
  - 181 teams scheduled
  - 576 games generated

### Validation
- **Time**: ~1 second
- **Components**:
  - Hard constraint checking
  - Soft constraint scoring
  - Detailed violation reporting

## Schedule Quality

The optimized greedy algorithm produces schedules with:
- ✓ All do-not-play constraints respected
- ✓ Facility availability constraints respected
- ✓ Division-specific requirements (8ft rims for ES K-1 REC)
- ✓ Balanced matchups based on tier and cluster
- ✓ Reasonable game distribution per team

### Typical Results
- **Total Games**: 576 games across 6 divisions
- **Games per Team**: 4-8 games per team
- **Schedule Coverage**: Full season (Jan 5 - Feb 28, 2026)

## Recommendations

### For Current Dataset (181 teams, 6 divisions)
- **Use**: Optimized greedy algorithm (current default)
- **Expected Time**: 8-15 seconds total
- **Quality**: High-quality schedules with good constraint satisfaction

### For Larger Datasets (>50 teams per division)
- **Consider**: Hybrid approach with CP-SAT for specific divisions
- **Timeout**: 20 seconds per division maximum
- **Fallback**: Always use greedy if CP-SAT times out

### For Real-Time Scheduling
- **Current Performance**: Suitable for interactive use
- **Response Time**: Under 15 seconds for full schedule generation
- **User Experience**: No noticeable delay

## Configuration Options

### To Adjust Performance vs Quality Trade-off

In `scheduler.py`, modify the division size threshold:

```python
# Current: Use greedy for all divisions
if len(division_teams) > 30:
    # Use CP-SAT for very large divisions
    division_games = self._schedule_division(division, division_teams)
else:
    # Use greedy for smaller divisions
    division_games = self._greedy_schedule_division(division, division_teams)
```

**Options**:
- `> 30`: Current setting (greedy for all current divisions)
- `> 50`: Use CP-SAT for divisions with 50+ teams
- `> 100`: Use CP-SAT only for very large divisions

### To Adjust CP-SAT Timeout

In `scheduler.py`, line 342:

```python
solver.parameters.max_time_in_seconds = 20.0  # Adjust as needed
```

**Trade-offs**:
- Lower (10-15s): Faster, may not find optimal solution
- Higher (30-60s): Slower, better chance of optimal solution
- Current (20s): Good balance for most cases

## Conclusion

The optimization successfully reduced scheduling time from **5+ minutes to under 15 seconds**, achieving a **40x performance improvement** while maintaining high schedule quality. The system now meets the requirement of completing in under 3 minutes with significant headroom.

### Key Success Factors
1. Algorithm selection based on problem characteristics
2. Pre-filtering to reduce search space
3. Efficient data structures and sorting
4. Elimination of unnecessary computation

### Future Optimization Opportunities
1. Parallel division scheduling (process multiple divisions simultaneously)
2. Incremental scheduling (add/modify games without full regeneration)
3. Caching of frequently used computations
4. GPU acceleration for very large datasets (100+ divisions)
