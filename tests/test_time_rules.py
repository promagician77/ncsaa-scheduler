"""
Test script to verify time rules are followed in the schedule.
Checks:
1. No games on Sunday
2. Weeknight games between 5PM-8:30PM
3. Saturday games between 8AM-6PM
"""

import sys
import os
from datetime import datetime, time

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sheets_reader import SheetsReader
from app.services.scheduler import ScheduleOptimizer

def test_time_rules():
    """Test that all time rules are followed."""
    print("=" * 60)
    print("TESTING TIME RULES")
    print("=" * 60)
    
    # Load data
    print("\nLoading data from Google Sheets...")
    reader = SheetsReader()
    teams, facilities, rules = reader.load_all_data()
    
    # Generate schedule
    print("\nGenerating schedule...")
    optimizer = ScheduleOptimizer(teams, facilities, rules)
    schedule = optimizer.optimize_schedule()
    
    print(f"\nTotal games generated: {len(schedule.games)}")
    
    # Define time limits
    WEEKNIGHT_START = time(17, 0)  # 5:00 PM
    WEEKNIGHT_END = time(20, 30)   # 8:30 PM
    SATURDAY_START = time(8, 0)    # 8:00 AM
    SATURDAY_END = time(18, 0)     # 6:00 PM
    
    # Track violations
    sunday_violations = []
    weeknight_violations = []
    saturday_violations = []
    
    # Check each game
    for game in schedule.games:
        game_date = game.time_slot.date
        game_start = game.time_slot.start_time
        game_end = game.time_slot.end_time
        day_of_week = game_date.weekday()  # 0=Monday, 6=Sunday
        day_name = game_date.strftime("%A")
        
        # Check for Sunday games
        if day_of_week == 6:
            sunday_violations.append({
                'game_id': game.id,
                'date': game_date,
                'day': day_name,
                'time': f"{game_start} - {game_end}"
            })
        
        # Check weeknight times (Monday-Friday)
        elif day_of_week < 5:
            if game_start < WEEKNIGHT_START or game_end > WEEKNIGHT_END:
                weeknight_violations.append({
                    'game_id': game.id,
                    'date': game_date,
                    'day': day_name,
                    'time': f"{game_start} - {game_end}",
                    'reason': f"Outside 5PM-8:30PM window"
                })
        
        # Check Saturday times
        elif day_of_week == 5:
            if game_start < SATURDAY_START or game_end > SATURDAY_END:
                saturday_violations.append({
                    'game_id': game.id,
                    'date': game_date,
                    'day': day_name,
                    'time': f"{game_start} - {game_end}",
                    'reason': f"Outside 8AM-6PM window"
                })
    
    # Report results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    # Sunday violations
    print(f"\n1. SUNDAY GAMES (Should be 0):")
    print(f"   Found: {len(sunday_violations)} violations")
    if sunday_violations:
        print("\n   [FAIL] Games scheduled on Sunday:")
        for v in sunday_violations[:10]:  # Show first 10
            print(f"   - {v['game_id']}: {v['date']} ({v['day']}) at {v['time']}")
    else:
        print("   [PASS] No Sunday games found")
    
    # Weeknight violations
    print(f"\n2. WEEKNIGHT TIME VIOLATIONS (Should be 0):")
    print(f"   Rule: Games between 5:00 PM - 8:30 PM")
    print(f"   Found: {len(weeknight_violations)} violations")
    if weeknight_violations:
        print("\n   [FAIL] Games outside weeknight window:")
        for v in weeknight_violations[:10]:  # Show first 10
            print(f"   - {v['game_id']}: {v['date']} ({v['day']}) at {v['time']} - {v['reason']}")
    else:
        print("   [PASS] All weeknight games within 5PM-8:30PM")
    
    # Saturday violations
    print(f"\n3. SATURDAY TIME VIOLATIONS (Should be 0):")
    print(f"   Rule: Games between 8:00 AM - 6:00 PM")
    print(f"   Found: {len(saturday_violations)} violations")
    if saturday_violations:
        print("\n   [FAIL] Games outside Saturday window:")
        for v in saturday_violations[:10]:  # Show first 10
            print(f"   - {v['game_id']}: {v['date']} ({v['day']}) at {v['time']} - {v['reason']}")
    else:
        print("   [PASS] All Saturday games within 8AM-6PM")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_violations = len(sunday_violations) + len(weeknight_violations) + len(saturday_violations)
    
    if total_violations == 0:
        print("\n[PASS] ALL TIME RULES FOLLOWED!")
        print("- No Sunday games")
        print("- All weeknight games between 5PM-8:30PM")
        print("- All Saturday games between 8AM-6PM")
    else:
        print(f"\n[FAIL] {total_violations} TOTAL VIOLATIONS FOUND")
        print(f"- Sunday games: {len(sunday_violations)}")
        print(f"- Weeknight violations: {len(weeknight_violations)}")
        print(f"- Saturday violations: {len(saturday_violations)}")
    
    print("\n" + "=" * 60)
    
    return total_violations == 0

if __name__ == "__main__":
    try:
        success = test_time_rules()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
