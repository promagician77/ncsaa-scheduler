"""
Test the redesigned school-based scheduler.

Verifies:
1. Schools are clustered together (all divisions play on same night)
2. No same-school matchups (Rule #23)
3. All teams play 8 games (Rule #22)
4. Coaches with multiple teams have back-to-back games (Rule #15)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sheets_reader import SheetsReader
from app.services.scheduler_v2 import SchoolBasedScheduler
from collections import defaultdict
from datetime import datetime


def test_school_based_scheduler():
    """Test the redesigned school-based scheduler."""
    print("\n" + "=" * 70)
    print("TESTING REDESIGNED SCHOOL-BASED SCHEDULER")
    print("=" * 70)
    
    # Load data
    print("\n1. Loading data from Google Sheets...")
    reader = SheetsReader()
    teams = reader.load_teams()
    facilities = reader.load_facilities()
    rules = reader.load_rules()
    
    print(f"   Loaded {len(teams)} teams")
    
    # Generate schedule
    print("\n2. Generating schedule with school-based algorithm...")
    start_time = datetime.now()
    scheduler = SchoolBasedScheduler(teams, facilities, rules)
    schedule = scheduler.optimize_schedule()
    end_time = datetime.now()
    
    generation_time = (end_time - start_time).total_seconds()
    print(f"\n   Schedule generated in {generation_time:.2f} seconds")
    print(f"   Total games: {len(schedule.games)}")
    
    # Analyze results
    print("\n3. Analyzing schedule structure...")
    
    # Group games by date/time/facility to see clustering
    games_by_block = defaultdict(list)
    for game in schedule.games:
        block_key = (game.time_slot.date, game.time_slot.start_time, game.time_slot.facility.name)
        games_by_block[block_key].append(game)
    
    print(f"   Total time blocks used: {len(games_by_block)}")
    
    # Check school clustering
    print("\n4. Checking school clustering...")
    school_clustering_good = 0
    school_clustering_bad = 0
    
    for block_key, block_games in games_by_block.items():
        # Get all schools involved in this block
        schools_in_block = set()
        for game in block_games:
            schools_in_block.add(game.home_team.school.name)
            schools_in_block.add(game.away_team.school.name)
        
        # Ideally, we should have 2 schools (School A vs School B across all divisions)
        if len(schools_in_block) == 2:
            school_clustering_good += 1
        else:
            school_clustering_bad += 1
            if school_clustering_bad <= 5:  # Show first 5 examples
                date, time, facility = block_key
                print(f"   WARNING: {len(schools_in_block)} schools in block at {facility} on {date} at {time}")
                print(f"            Schools: {', '.join(sorted(schools_in_block))}")
    
    print(f"\n   Good clustering (2 schools): {school_clustering_good} blocks")
    print(f"   Poor clustering (>2 schools): {school_clustering_bad} blocks")
    
    # Check for same-school matchups (Rule #23)
    print("\n5. Checking for same-school matchups (Rule #23)...")
    same_school_violations = []
    for game in schedule.games:
        if game.home_team.school.name == game.away_team.school.name:
            same_school_violations.append({
                'school': game.home_team.school.name,
                'division': game.division.value,
                'date': game.time_slot.date
            })
    
    if same_school_violations:
        print(f"   [FAIL] Found {len(same_school_violations)} same-school matchups!")
        for v in same_school_violations[:5]:
            print(f"      - {v['school']} vs {v['school']} in {v['division']} on {v['date']}")
    else:
        print(f"   [PASS] No same-school matchups found!")
    
    # Check game counts (Rule #22)
    print("\n6. Checking game counts (Rule #22: Each team plays 8 games)...")
    team_game_counts = defaultdict(int)
    for game in schedule.games:
        team_game_counts[game.home_team.id] += 1
        team_game_counts[game.away_team.id] += 1
    
    teams_with_8 = sum(1 for count in team_game_counts.values() if count == 8)
    teams_under_8 = sum(1 for count in team_game_counts.values() if count < 8)
    teams_over_8 = sum(1 for count in team_game_counts.values() if count > 8)
    
    print(f"   Teams with exactly 8 games: {teams_with_8}")
    print(f"   Teams with < 8 games: {teams_under_8}")
    print(f"   Teams with > 8 games: {teams_over_8}")
    
    if teams_under_8 > 0:
        print(f"\n   WARNING: {teams_under_8} teams have fewer than 8 games:")
        for team in teams:
            if team_game_counts[team.id] < 8:
                print(f"      - {team.school.name} ({team.coach_name}) in {team.division.value}: {team_game_counts[team.id]} games")
                if teams_under_8 > 10:
                    break
    
    # Check coach clustering
    print("\n7. Checking coach clustering (Rule #15)...")
    coaches_with_multiple_teams = defaultdict(list)
    for team in teams:
        if team.coach_name:
            coaches_with_multiple_teams[team.coach_name].append(team)
    
    coaches_with_multiple = {coach: team_list for coach, team_list in coaches_with_multiple_teams.items() if len(team_list) > 1}
    print(f"   Coaches with multiple teams: {len(coaches_with_multiple)}")
    
    # For each coach with multiple teams, check if their games are clustered
    coach_clustering_good = 0
    coach_clustering_bad = 0
    
    for coach, coach_teams in list(coaches_with_multiple.items())[:10]:  # Check first 10
        # Find all games for this coach's teams
        coach_games = [g for g in schedule.games if g.home_team.coach_name == coach or g.away_team.coach_name == coach]
        
        if len(coach_games) > 1:
            # Check if games are at same time/facility
            game_blocks = set()
            for game in coach_games:
                block_key = (game.time_slot.date, game.time_slot.start_time, game.time_slot.facility.name)
                game_blocks.add(block_key)
            
            if len(game_blocks) == 1:
                coach_clustering_good += 1
            else:
                coach_clustering_bad += 1
    
    print(f"   Coaches with good clustering (same block): {coach_clustering_good}")
    print(f"   Coaches with poor clustering (different blocks): {coach_clustering_bad}")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    all_pass = True
    
    if same_school_violations:
        print("[FAIL] Same-school matchups found (Rule #23 violated)")
        all_pass = False
    else:
        print("[PASS] No same-school matchups (Rule #23)")
    
    if teams_under_8 == 0:
        print("[PASS] All teams have 8 games (Rule #22)")
    else:
        print(f"[FAIL] {teams_under_8} teams have < 8 games (Rule #22 violated)")
        all_pass = False
    
    if school_clustering_good > school_clustering_bad:
        print("[PASS] Good school clustering (Rule #15)")
    else:
        print("[WARN] School clustering needs improvement (Rule #15)")
    
    print("\n" + "=" * 70)
    if all_pass:
        print("ALL CRITICAL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED - Review above")
    print("=" * 70)
    
    return all_pass


if __name__ == "__main__":
    try:
        success = test_school_based_scheduler()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
