"""
Test script to verify the critical bug fixes:
1. Teams cannot be scheduled in multiple locations at the same time
2. Teams from the same school cannot play simultaneously
3. Teams play each other at most 2 times
"""

import sys
from collections import defaultdict
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, '.')

from app.services.sheets_reader import SheetsReader
from app.services.scheduler import ScheduleOptimizer

def test_schedule_constraints():
    """Test that the schedule meets all critical constraints."""
    print("=" * 80)
    print("TESTING CRITICAL BUG FIXES")
    print("=" * 80)
    
    # Load data from Google Sheets
    print("\n1. Loading data from Google Sheets...")
    reader = SheetsReader()
    
    try:
        rules = reader.load_rules()
        teams = reader.load_teams()
        facilities = reader.load_facilities()
        
        print(f"   Loaded {len(teams)} teams")
        print(f"   Loaded {len(facilities)} facilities")
        
        # Create scheduler
        print("\n2. Creating schedule...")
        optimizer = ScheduleOptimizer(teams, facilities, rules)
        schedule = optimizer.optimize_schedule()
        
        print(f"   Generated {len(schedule.games)} games")
        
        # Test 1: Check for facility/court conflicts
        print("\n3. Testing for facility/court conflicts (multiple games at same court)...")
        facility_court_games = defaultdict(list)
        facility_conflicts = []
        
        for game in schedule.games:
            key = (game.time_slot.date, game.time_slot.start_time, 
                   game.time_slot.facility.name, game.time_slot.court_number)
            facility_court_games[key].append(game)
        
        for key, games in facility_court_games.items():
            if len(games) > 1:
                facility_conflicts.append(
                    f"   ERROR: {len(games)} games at {key[2]} Court {key[3]} on {key[0]} at {key[1]}"
                )
                for g in games:
                    facility_conflicts.append(
                        f"     - {g.division.value}: {g.home_team.school.name} vs {g.away_team.school.name}"
                    )
        
        if facility_conflicts:
            print(f"   FAILED: Found {len([c for c in facility_conflicts if 'ERROR' in c])} facility/court conflicts:")
            for error in facility_conflicts[:30]:  # Show first 30
                print(error)
        else:
            print("   PASSED: No facility/court conflicts detected!")
        
        # Test 2: Check for team double-booking
        print("\n4. Testing for team double-booking (same team at multiple locations)...")
        time_slot_teams = defaultdict(lambda: defaultdict(list))
        double_booking_errors = []
        
        for game in schedule.games:
            time_key = (game.time_slot.date, game.time_slot.start_time)
            time_slot_teams[time_key][game.home_team.id].append(game)
            time_slot_teams[time_key][game.away_team.id].append(game)
        
        for time_key, teams_at_time in time_slot_teams.items():
            for team_id, games in teams_at_time.items():
                if len(games) > 1:
                    double_booking_errors.append(
                        f"   ERROR: Team {team_id} scheduled for {len(games)} games at {time_key[0]} {time_key[1]}"
                    )
                    for g in games:
                        double_booking_errors.append(
                            f"     - {g.home_team.school.name} vs {g.away_team.school.name} at {g.time_slot.facility.name}"
                        )
        
        if double_booking_errors:
            print(f"   FAILED: Found {len(double_booking_errors)} double-booking errors:")
            for error in double_booking_errors[:20]:  # Show first 20
                print(error)
        else:
            print("   PASSED: No team double-booking detected!")
        
        # Test 3: Check for same-school conflicts
        print("\n5. Testing for same-school conflicts...")
        same_school_errors = []
        
        for time_key, teams_at_time in time_slot_teams.items():
            schools_at_time = defaultdict(list)
            
            for game in schedule.games:
                if (game.time_slot.date, game.time_slot.start_time) == time_key:
                    schools_at_time[game.home_team.school.name].append(game)
                    schools_at_time[game.away_team.school.name].append(game)
            
            for school_name, games in schools_at_time.items():
                if len(games) > 1:
                    same_school_errors.append(
                        f"   ERROR: {school_name} has {len(games)} teams playing at {time_key[0]} {time_key[1]}"
                    )
        
        if same_school_errors:
            print(f"   FAILED: Found {len(same_school_errors)} same-school conflicts:")
            for error in same_school_errors[:20]:  # Show first 20
                print(error)
        else:
            print("   PASSED: No same-school conflicts detected!")
        
        # Test 4: Check for excessive rematches
        print("\n6. Testing for excessive rematches (teams playing >2 times)...")
        matchup_counts = defaultdict(int)
        
        for game in schedule.games:
            matchup_key = tuple(sorted([game.home_team.id, game.away_team.id]))
            matchup_counts[matchup_key] += 1
        
        excessive_rematches = []
        for matchup_key, count in matchup_counts.items():
            if count > 2:
                excessive_rematches.append(
                    f"   ERROR: {matchup_key[0]} vs {matchup_key[1]} scheduled {count} times (max 2)"
                )
        
        if excessive_rematches:
            print(f"   FAILED: Found {len(excessive_rematches)} excessive rematches:")
            for error in excessive_rematches[:20]:  # Show first 20
                print(error)
        else:
            print("   PASSED: No excessive rematches detected!")
        
        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        facility_error_count = len([c for c in facility_conflicts if 'ERROR' in c])
        total_errors = facility_error_count + len(double_booking_errors) + len(same_school_errors) + len(excessive_rematches)
        
        if total_errors == 0:
            print("[PASS] ALL TESTS PASSED!")
            print("[PASS] No facility/court conflicts")
            print("[PASS] No team double-booking")
            print("[PASS] No same-school conflicts")
            print("[PASS] No excessive rematches")
            print("\nThe critical bugs have been FIXED!")
        else:
            print(f"[FAIL] TESTS FAILED with {total_errors} errors")
            print(f"  - Facility/court conflicts: {facility_error_count}")
            print(f"  - Double-booking errors: {len(double_booking_errors)}")
            print(f"  - Same-school conflicts: {len(same_school_errors)}")
            print(f"  - Excessive rematches: {len(excessive_rematches)}")
        
        print("=" * 80)
        
        return total_errors == 0
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_schedule_constraints()
    sys.exit(0 if success else 1)
