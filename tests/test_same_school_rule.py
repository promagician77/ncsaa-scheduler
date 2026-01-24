"""
Test to verify Rule #23: Teams from the same school should NEVER play each other.

This test ensures that the scheduler correctly prevents same-school matchups.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sheets_reader import SheetsReader
from app.services.scheduler import ScheduleOptimizer
from collections import defaultdict


def test_same_school_rule():
    """
    Test that no teams from the same school are scheduled to play each other.
    Rule #23: Some schools have 2 teams in a division. They should never play each other.
    """
    print("\n" + "=" * 70)
    print("TESTING RULE #23: Same School Teams Should NEVER Play Each Other")
    print("=" * 70)
    
    # Load data
    print("\n1. Loading data from Google Sheets...")
    reader = SheetsReader()
    teams = reader.load_teams()
    facilities = reader.load_facilities()
    rules = reader.load_rules()
    
    print(f"   Loaded {len(teams)} teams")
    
    # Find schools with multiple teams in the same division
    schools_by_division = defaultdict(lambda: defaultdict(list))
    for team in teams:
        schools_by_division[team.division.value][team.school.name].append(team)
    
    print("\n2. Schools with multiple teams in same division:")
    multi_team_schools = []
    for division, schools in schools_by_division.items():
        for school_name, school_teams in schools.items():
            if len(school_teams) > 1:
                multi_team_schools.append((division, school_name, school_teams))
                print(f"   {division}: {school_name} has {len(school_teams)} teams")
                for team in school_teams:
                    print(f"      - {team.school.name} ({team.coach_name})")
    
    if not multi_team_schools:
        print("   No schools with multiple teams in same division found")
        return
    
    # Generate schedule
    print("\n3. Generating schedule...")
    optimizer = ScheduleOptimizer(teams, facilities, rules)
    schedule = optimizer.optimize_schedule()
    
    print(f"   Generated {len(schedule.games)} games")
    
    # Check for same-school matchups
    print("\n4. Checking for same-school matchups (Rule #23 violations)...")
    violations = []
    
    for game in schedule.games:
        if game.home_team.school.name == game.away_team.school.name:
            violations.append({
                'division': game.division.value,
                'school': game.home_team.school.name,
                'home_team': f"{game.home_team.school.name} ({game.home_team.coach_name})",
                'away_team': f"{game.away_team.school.name} ({game.away_team.coach_name})",
                'date': game.time_slot.date,
                'time': game.time_slot.start_time,
                'facility': game.time_slot.facility.name
            })
    
    # Report results
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    
    if violations:
        print(f"\n[FAIL] Found {len(violations)} same-school matchups (Rule #23 violations):\n")
        for v in violations[:20]:  # Show first 20
            print(f"  Division: {v['division']}")
            print(f"  School: {v['school']}")
            print(f"  Matchup: {v['home_team']} vs {v['away_team']}")
            print(f"  Date/Time: {v['date']} at {v['time']}")
            print(f"  Facility: {v['facility']}")
            print()
        
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more violations")
        
        print("\n" + "=" * 70)
        print("TEST FAILED - Same-school matchups found!")
        print("=" * 70)
        return False
    else:
        print("\n[PASS] No same-school matchups found!")
        print("Rule #23 is correctly enforced.")
        print("\n" + "=" * 70)
        print("TEST PASSED")
        print("=" * 70)
        return True


if __name__ == "__main__":
    try:
        success = test_same_school_rule()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
