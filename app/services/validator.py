"""
Schedule validation module for the NCSAA Basketball Scheduling System.
Validates schedules against all hard and soft constraints.
"""

from datetime import timedelta
from typing import List, Dict, Set
from collections import defaultdict

from app.models import (
    Schedule, Game, Team, SchedulingConstraint,
    ScheduleValidationResult, TeamScheduleStats
)
from app.core.config import (
    MAX_GAMES_PER_7_DAYS, MAX_GAMES_PER_14_DAYS,
    MAX_DOUBLEHEADERS_PER_SEASON, DOUBLEHEADER_BREAK_MINUTES,
    PRIORITY_WEIGHTS
)


class ScheduleValidator:
    """
    Validates basketball game schedules against all constraints.
    Checks both hard constraints (must be satisfied) and soft constraints (preferences).
    """
    
    def __init__(self):
        """Initialize the validator."""
        pass
    
    def validate_schedule(self, schedule: Schedule) -> ScheduleValidationResult:
        """
        Validate a complete schedule against all constraints.
        
        Args:
            schedule: The schedule to validate
            
        Returns:
            ScheduleValidationResult with all violations found
        """
        result = ScheduleValidationResult(is_valid=True)
        
        print("\n" + "=" * 60)
        print("Validating schedule...")
        print("=" * 60)
        
        # Run all validation checks
        self._check_facility_court_conflicts(schedule, result)  # NEW: Check for facility/court double-booking
        self._check_time_slot_conflicts(schedule, result)
        self._check_team_double_booking(schedule, result)  # NEW: Check for teams in multiple locations at once
        self._check_same_school_conflicts(schedule, result)  # NEW: Check for same school conflicts
        self._check_duplicate_matchups(schedule, result)  # NEW: Check for excessive rematches
        self._check_team_game_frequency(schedule, result)
        self._check_doubleheader_limits(schedule, result)
        self._check_do_not_play_constraints(schedule, result)
        self._check_facility_availability(schedule, result)
        self._check_home_away_balance(schedule, result)
        self._check_rival_matchups(schedule, result)
        
        # Print summary
        print("\n" + "=" * 60)
        print("Validation Results:")
        print("=" * 60)
        print(f"Valid: {result.is_valid}")
        print(f"Hard Constraint Violations: {len(result.hard_constraint_violations)}")
        print(f"Soft Constraint Violations: {len(result.soft_constraint_violations)}")
        print(f"Total Penalty Score: {result.total_penalty_score:.2f}")
        
        if result.hard_constraint_violations:
            print("\nHard Constraint Violations:")
            for violation in result.hard_constraint_violations[:10]:  # Show first 10
                print(f"  - {violation.constraint_type}: {violation.description}")
        
        if result.soft_constraint_violations:
            print(f"\nSoft Constraint Violations: {len(result.soft_constraint_violations)}")
        
        print("=" * 60)
        
        return result
    
    def _check_time_slot_conflicts(self, schedule: Schedule, result: ScheduleValidationResult):
        """Check for time slot conflicts (same facility/court at same time)."""
        # Group games by time slot key
        slot_games = defaultdict(list)
        
        for game in schedule.games:
            slot = game.time_slot
            key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
            slot_games[key].append(game)
        
        # Check for conflicts
        for key, games in slot_games.items():
            if len(games) > 1:
                constraint = SchedulingConstraint(
                    constraint_type="time_slot_conflict",
                    severity="hard",
                    description=f"Multiple games scheduled at {key[0]} {key[1]} at {key[2]} court {key[3]}",
                    affected_games=games,
                    penalty_score=1000.0
                )
                result.add_violation(constraint)
    
    def _check_team_game_frequency(self, schedule: Schedule, result: ScheduleValidationResult):
        """Check if teams are playing too many games in short time periods."""
        # Get all unique teams
        teams = set()
        for game in schedule.games:
            teams.add(game.home_team)
            teams.add(game.away_team)
        
        for team in teams:
            team_games = sorted(schedule.get_team_games(team), key=lambda g: g.time_slot.date)
            
            # Check 7-day windows
            for i, game in enumerate(team_games):
                games_in_7_days = [game]
                
                for j in range(i + 1, len(team_games)):
                    other_game = team_games[j]
                    days_diff = (other_game.time_slot.date - game.time_slot.date).days
                    
                    if days_diff <= 7:
                        games_in_7_days.append(other_game)
                    else:
                        break
                
                if len(games_in_7_days) > MAX_GAMES_PER_7_DAYS:
                    constraint = SchedulingConstraint(
                        constraint_type="too_many_games_per_week",
                        severity="hard",
                        description=f"{team.id} has {len(games_in_7_days)} games in 7 days (max {MAX_GAMES_PER_7_DAYS})",
                        affected_teams=[team],
                        affected_games=games_in_7_days,
                        penalty_score=500.0
                    )
                    result.add_violation(constraint)
            
            # Check 14-day windows
            for i, game in enumerate(team_games):
                games_in_14_days = [game]
                
                for j in range(i + 1, len(team_games)):
                    other_game = team_games[j]
                    days_diff = (other_game.time_slot.date - game.time_slot.date).days
                    
                    if days_diff <= 14:
                        games_in_14_days.append(other_game)
                    else:
                        break
                
                if len(games_in_14_days) > MAX_GAMES_PER_14_DAYS:
                    constraint = SchedulingConstraint(
                        constraint_type="too_many_games_per_2weeks",
                        severity="hard",
                        description=f"{team.id} has {len(games_in_14_days)} games in 14 days (max {MAX_GAMES_PER_14_DAYS})",
                        affected_teams=[team],
                        affected_games=games_in_14_days,
                        penalty_score=300.0
                    )
                    result.add_violation(constraint)
    
    def _check_doubleheader_limits(self, schedule: Schedule, result: ScheduleValidationResult):
        """Check if teams exceed doubleheader limits."""
        # Get all unique teams
        teams = set()
        for game in schedule.games:
            teams.add(game.home_team)
            teams.add(game.away_team)
        
        for team in teams:
            team_games = sorted(schedule.get_team_games(team), key=lambda g: (g.time_slot.date, g.time_slot.start_time))
            
            doubleheader_count = 0
            
            for i in range(len(team_games) - 1):
                game1 = team_games[i]
                game2 = team_games[i + 1]
                
                # Check if same day
                if game1.time_slot.date == game2.time_slot.date:
                    # Calculate time between games
                    time1_end = game1.time_slot.end_time
                    time2_start = game2.time_slot.start_time
                    
                    # Convert to minutes
                    end_minutes = time1_end.hour * 60 + time1_end.minute
                    start_minutes = time2_start.hour * 60 + time2_start.minute
                    gap_minutes = start_minutes - end_minutes
                    
                    # If games are close together, it's a doubleheader
                    if 0 <= gap_minutes <= DOUBLEHEADER_BREAK_MINUTES + 30:
                        doubleheader_count += 1
                        game1.is_doubleheader = True
                        game2.is_doubleheader = True
            
            if doubleheader_count > MAX_DOUBLEHEADERS_PER_SEASON:
                constraint = SchedulingConstraint(
                    constraint_type="too_many_doubleheaders",
                    severity="hard",
                    description=f"{team.id} has {doubleheader_count} doubleheaders (max {MAX_DOUBLEHEADERS_PER_SEASON})",
                    affected_teams=[team],
                    penalty_score=400.0
                )
                result.add_violation(constraint)
    
    def _check_do_not_play_constraints(self, schedule: Schedule, result: ScheduleValidationResult):
        """Check if any do-not-play constraints are violated."""
        for game in schedule.games:
            team1 = game.home_team
            team2 = game.away_team
            
            if team2.id in team1.do_not_play or team1.id in team2.do_not_play:
                constraint = SchedulingConstraint(
                    constraint_type="do_not_play_violation",
                    severity="hard",
                    description=f"{team1.id} and {team2.id} should not play each other",
                    affected_teams=[team1, team2],
                    affected_games=[game],
                    penalty_score=PRIORITY_WEIGHTS['respect_do_not_play']
                )
                result.add_violation(constraint)
    
    def _check_facility_availability(self, schedule: Schedule, result: ScheduleValidationResult):
        """Check if games are scheduled at unavailable facilities."""
        for game in schedule.games:
            facility = game.time_slot.facility
            game_date = game.time_slot.date
            
            if not facility.is_available(game_date):
                constraint = SchedulingConstraint(
                    constraint_type="facility_unavailable",
                    severity="hard",
                    description=f"Facility {facility.name} is not available on {game_date}",
                    affected_games=[game],
                    penalty_score=PRIORITY_WEIGHTS['facility_availability']
                )
                result.add_violation(constraint)
    
    def _check_home_away_balance(self, schedule: Schedule, result: ScheduleValidationResult):
        """Check if teams have balanced home/away games (soft constraint)."""
        # Get all unique teams
        teams = set()
        for game in schedule.games:
            teams.add(game.home_team)
            teams.add(game.away_team)
        
        for team in teams:
            stats = self.get_team_stats(team, schedule)
            
            if stats.total_games == 0:
                continue
            
            # Calculate imbalance
            imbalance = abs(stats.home_games - stats.away_games)
            
            # Allow some imbalance, but penalize large differences
            if imbalance > 2:
                constraint = SchedulingConstraint(
                    constraint_type="home_away_imbalance",
                    severity="soft",
                    description=f"{team.id} has imbalanced home/away: {stats.home_games} home, {stats.away_games} away",
                    affected_teams=[team],
                    penalty_score=imbalance * 10.0
                )
                result.add_violation(constraint)
    
    def _check_rival_matchups(self, schedule: Schedule, result: ScheduleValidationResult):
        """Check if rival teams are scheduled to play (soft constraint)."""
        # Get all unique teams
        teams = set()
        for game in schedule.games:
            teams.add(game.home_team)
            teams.add(game.away_team)
        
        for team in teams:
            if not team.rivals:
                continue
            
            team_games = schedule.get_team_games(team)
            opponents = set()
            
            for game in team_games:
                opponent = game.get_opponent(team)
                if opponent:
                    opponents.add(opponent.id)
            
            # Check if all rivals are scheduled
            missing_rivals = team.rivals - opponents
            
            if missing_rivals:
                constraint = SchedulingConstraint(
                    constraint_type="missing_rival_matchup",
                    severity="soft",
                    description=f"{team.id} is missing games against rivals: {', '.join(missing_rivals)}",
                    affected_teams=[team],
                    penalty_score=len(missing_rivals) * PRIORITY_WEIGHTS['respect_rivals']
                )
                result.add_violation(constraint)
    
    def get_team_stats(self, team: Team, schedule: Schedule) -> TeamScheduleStats:
        """
        Calculate statistics for a team's schedule.
        
        Args:
            team: The team to analyze
            schedule: The complete schedule
            
        Returns:
            TeamScheduleStats with all statistics
        """
        stats = TeamScheduleStats(team=team)
        
        team_games = schedule.get_team_games(team)
        stats.total_games = len(team_games)
        
        for game in team_games:
            if game.is_home_game(team):
                stats.home_games += 1
            else:
                stats.away_games += 1
            
            if game.is_doubleheader:
                stats.doubleheaders += 1
            
            opponent = game.get_opponent(team)
            if opponent:
                stats.opponents.append(opponent)
            
            # Track games by week
            if schedule.season_start:
                week_num = (game.time_slot.date - schedule.season_start).days // 7
                stats.games_by_week[week_num] = stats.games_by_week.get(week_num, 0) + 1
        
        return stats
    
    def generate_schedule_report(self, schedule: Schedule) -> str:
        """
        Generate a comprehensive report of the schedule.
        
        Args:
            schedule: The schedule to report on
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("SCHEDULE REPORT")
        report.append("=" * 80)
        report.append(f"Season: {schedule.season_start} to {schedule.season_end}")
        report.append(f"Total Games: {len(schedule.games)}")
        report.append("")
        
        # Games by division
        report.append("Games by Division:")
        from app.models import Division
        for division in Division:
            div_games = schedule.get_games_by_division(division)
            if div_games:
                report.append(f"  {division.value}: {len(div_games)} games")
        report.append("")
        
        # Games by date
        report.append("Games by Date:")
        games_by_date = defaultdict(list)
        for game in schedule.games:
            games_by_date[game.time_slot.date].append(game)
        
        for game_date in sorted(games_by_date.keys()):
            games = games_by_date[game_date]
            report.append(f"  {game_date}: {len(games)} games")
        report.append("")
        
        # Team statistics
        report.append("Team Statistics:")
        teams = set()
        for game in schedule.games:
            teams.add(game.home_team)
            teams.add(game.away_team)
        
        for team in sorted(teams, key=lambda t: t.id):
            stats = self.get_team_stats(team, schedule)
            report.append(f"  {team.id}:")
            report.append(f"    Total Games: {stats.total_games}")
            report.append(f"    Home: {stats.home_games}, Away: {stats.away_games}")
            if stats.doubleheaders > 0:
                report.append(f"    Doubleheaders: {stats.doubleheaders}")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def _check_facility_court_conflicts(self, schedule: Schedule, result: ScheduleValidationResult):
        """
        Check for multiple games scheduled at the same facility/court at the same time.
        This is a CRITICAL constraint - a court can only host one game at a time.
        """
        # Group games by facility/court/time
        facility_court_games = defaultdict(list)
        
        for game in schedule.games:
            slot = game.time_slot
            key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
            facility_court_games[key].append(game)
        
        # Check for conflicts
        for key, games in facility_court_games.items():
            if len(games) > 1:
                constraint = SchedulingConstraint(
                    constraint_type="facility_court_conflict",
                    severity="hard",
                    description=f"Multiple games ({len(games)}) scheduled at {key[2]} Court {key[3]} on {key[0]} at {key[1]}",
                    affected_games=games,
                    penalty_score=3000.0  # Highest penalty - physically impossible
                )
                result.add_violation(constraint)
    
    def _check_team_double_booking(self, schedule: Schedule, result: ScheduleValidationResult):
        """
        Check for teams scheduled to play in multiple locations at the same time.
        This is a CRITICAL constraint - teams cannot be in two places at once.
        """
        # Group games by time slot (date + start time)
        time_slot_games = defaultdict(list)
        
        for game in schedule.games:
            slot = game.time_slot
            time_key = (slot.date, slot.start_time)
            time_slot_games[time_key].append(game)
        
        # Check each time slot for teams appearing multiple times
        for time_key, games in time_slot_games.items():
            team_appearances = defaultdict(list)
            
            for game in games:
                team_appearances[game.home_team.id].append(game)
                team_appearances[game.away_team.id].append(game)
            
            # Check if any team appears more than once at this time
            for team_id, team_games in team_appearances.items():
                if len(team_games) > 1:
                    constraint = SchedulingConstraint(
                        constraint_type="team_double_booking",
                        severity="hard",
                        description=f"Team {team_id} is scheduled to play {len(team_games)} games simultaneously at {time_key[0]} {time_key[1]}",
                        affected_games=team_games,
                        penalty_score=2000.0  # Very high penalty - this is physically impossible
                    )
                    result.add_violation(constraint)
    
    def _check_same_school_conflicts(self, schedule: Schedule, result: ScheduleValidationResult):
        """
        Check for teams from the same school playing at the same time.
        This is a hard constraint to avoid scheduling conflicts.
        """
        # Group games by time slot
        time_slot_games = defaultdict(list)
        
        for game in schedule.games:
            slot = game.time_slot
            time_key = (slot.date, slot.start_time)
            time_slot_games[time_key].append(game)
        
        # Check each time slot for same-school conflicts
        for time_key, games in time_slot_games.items():
            schools_playing = defaultdict(list)
            
            for game in games:
                schools_playing[game.home_team.school.name].append(game)
                schools_playing[game.away_team.school.name].append(game)
            
            # Check if any school has multiple teams playing
            for school_name, school_games in schools_playing.items():
                if len(school_games) > 1:
                    constraint = SchedulingConstraint(
                        constraint_type="same_school_conflict",
                        severity="hard",
                        description=f"{school_name} has {len(school_games)} teams playing simultaneously at {time_key[0]} {time_key[1]}",
                        affected_games=school_games,
                        penalty_score=1500.0
                    )
                    result.add_violation(constraint)
    
    def _check_duplicate_matchups(self, schedule: Schedule, result: ScheduleValidationResult):
        """
        Check for teams playing each other more than twice.
        Teams should play each other at most 2 times in a season.
        """
        matchup_counts = defaultdict(int)
        matchup_games = defaultdict(list)
        
        for game in schedule.games:
            matchup_key = tuple(sorted([game.home_team.id, game.away_team.id]))
            matchup_counts[matchup_key] += 1
            matchup_games[matchup_key].append(game)
        
        # Check for excessive rematches
        for matchup_key, count in matchup_counts.items():
            if count > 2:  # Teams should play at most twice
                constraint = SchedulingConstraint(
                    constraint_type="excessive_rematches",
                    severity="hard",
                    description=f"Teams {matchup_key[0]} and {matchup_key[1]} play each other {count} times (max 2)",
                    affected_games=matchup_games[matchup_key],
                    penalty_score=800.0
                )
                result.add_violation(constraint)