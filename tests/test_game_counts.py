"""Test script to check game counts for all teams."""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sheets_reader import SheetsReader
from app.services.scheduler import ScheduleOptimizer

print("Loading data...")
r = SheetsReader()
teams, facilities, rules = r.load_all_data()

print("Generating schedule...")
optimizer = ScheduleOptimizer(teams, facilities, rules)
schedule = optimizer.optimize_schedule()

print('\n=== FINAL GAME COUNT CHECK ===\n')

# Count games per team
team_counts = {}
for game in schedule.games:
    team_counts.setdefault(game.home_team.id, 0)
    team_counts.setdefault(game.away_team.id, 0)
    team_counts[game.home_team.id] += 1
    team_counts[game.away_team.id] += 1

under_8 = {tid: count for tid, count in team_counts.items() if count < 8}
exactly_8 = {tid: count for tid, count in team_counts.items() if count == 8}
over_8 = {tid: count for tid, count in team_counts.items() if count > 8}

print(f'Total teams: {len(team_counts)}')
print(f'Teams with exactly 8 games: {len(exactly_8)} ({len(exactly_8)/len(team_counts)*100:.1f}%)')
print(f'Teams with < 8 games: {len(under_8)} ({len(under_8)/len(team_counts)*100:.1f}%)')
print(f'Teams with > 8 games: {len(over_8)} ({len(over_8)/len(team_counts)*100:.1f}%)')

if under_8:
    print(f'\nTeams with < 8 games (showing first 20):')
    for tid, count in sorted(under_8.items(), key=lambda x: x[1])[:20]:
        print(f'  {tid}: {count} games')

if over_8:
    print(f'\nTeams with > 8 games (showing first 10):')
    for tid, count in sorted(over_8.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f'  {tid}: {count} games')
