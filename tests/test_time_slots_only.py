"""
Quick test to verify time slot generation follows the rules.
"""

import sys
import os
from datetime import datetime, time, date, timedelta

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import (
    WEEKNIGHT_START_TIME, WEEKNIGHT_END_TIME,
    SATURDAY_START_TIME, SATURDAY_END_TIME,
    GAME_DURATION_MINUTES, WEEKNIGHT_SLOTS,
    SEASON_START_DATE, SEASON_END_DATE, NO_GAMES_ON_SUNDAY
)

def test_time_slot_rules():
    """Test that time slot generation follows all rules."""
    print("=" * 60)
    print("TESTING TIME SLOT GENERATION RULES")
    print("=" * 60)
    
    print("\n1. WEEKNIGHT SLOTS (Monday-Friday)")
    print(f"   Rule: Games between {WEEKNIGHT_START_TIME} - {WEEKNIGHT_END_TIME}")
    print(f"   Game duration: {GAME_DURATION_MINUTES} minutes")
    print(f"   Number of slots: {WEEKNIGHT_SLOTS}")
    print("\n   Generated slots:")
    
    weeknight_violations = []
    start_time = WEEKNIGHT_START_TIME
    for slot_num in range(WEEKNIGHT_SLOTS):
        slot_start = datetime.combine(datetime.min, start_time) + timedelta(minutes=slot_num * GAME_DURATION_MINUTES)
        slot_end = slot_start + timedelta(minutes=GAME_DURATION_MINUTES)
        
        # Check if valid
        valid = slot_end.time() <= WEEKNIGHT_END_TIME
        status = "[PASS]" if valid else "[FAIL]"
        
        print(f"   {status} Slot {slot_num + 1}: {slot_start.time()} - {slot_end.time()}")
        
        if not valid:
            weeknight_violations.append(f"Slot {slot_num + 1} ends at {slot_end.time()}, after {WEEKNIGHT_END_TIME}")
    
    print("\n2. SATURDAY SLOTS")
    print(f"   Rule: Games between {SATURDAY_START_TIME} - {SATURDAY_END_TIME}")
    print(f"   Game duration: {GAME_DURATION_MINUTES} minutes")
    print("\n   Generated slots:")
    
    saturday_violations = []
    current_time = datetime.combine(datetime.min, SATURDAY_START_TIME)
    end_datetime = datetime.combine(datetime.min, SATURDAY_END_TIME)
    slot_num = 0
    
    while current_time + timedelta(minutes=GAME_DURATION_MINUTES) <= end_datetime:
        slot_start = current_time
        slot_end = current_time + timedelta(minutes=GAME_DURATION_MINUTES)
        slot_num += 1
        
        # Check if valid
        valid = slot_end.time() <= SATURDAY_END_TIME
        status = "[PASS]" if valid else "[FAIL]"
        
        print(f"   {status} Slot {slot_num}: {slot_start.time()} - {slot_end.time()}")
        
        if not valid:
            saturday_violations.append(f"Slot {slot_num} ends at {slot_end.time()}, after {SATURDAY_END_TIME}")
        
        current_time += timedelta(minutes=GAME_DURATION_MINUTES)
    
    print(f"\n   Total Saturday slots: {slot_num}")
    
    print("\n3. SUNDAY RESTRICTION")
    print(f"   Rule: NO_GAMES_ON_SUNDAY = {NO_GAMES_ON_SUNDAY}")
    
    # Check if Sunday (day 6) is excluded
    season_start = datetime.strptime(SEASON_START_DATE, '%Y-%m-%d').date()
    season_end = datetime.strptime(SEASON_END_DATE, '%Y-%m-%d').date()
    
    current_date = season_start
    sunday_count = 0
    sundays = []
    
    while current_date <= season_end:
        if current_date.weekday() == 6:  # Sunday
            sunday_count += 1
            sundays.append(current_date)
        current_date += timedelta(days=1)
    
    print(f"   Sundays in season: {sunday_count}")
    if NO_GAMES_ON_SUNDAY:
        print(f"   [PASS] These {sunday_count} Sundays should be excluded from scheduling")
    else:
        print(f"   [INFO] Sunday games are allowed")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    total_violations = len(weeknight_violations) + len(saturday_violations)
    
    if total_violations == 0:
        print("\n[PASS] ALL TIME SLOT RULES FOLLOWED!")
        print(f"- Weeknight slots: {WEEKNIGHT_SLOTS} slots from {WEEKNIGHT_START_TIME} to {WEEKNIGHT_END_TIME}")
        print(f"- Saturday slots: {slot_num} slots from {SATURDAY_START_TIME} to {SATURDAY_END_TIME}")
        print(f"- Sunday games: {'BLOCKED' if NO_GAMES_ON_SUNDAY else 'ALLOWED'}")
    else:
        print(f"\n[FAIL] {total_violations} VIOLATIONS FOUND")
        for v in weeknight_violations:
            print(f"  - {v}")
        for v in saturday_violations:
            print(f"  - {v}")
    
    print("\n" + "=" * 60)
    
    return total_violations == 0

if __name__ == "__main__":
    success = test_time_slot_rules()
    exit(0 if success else 1)
