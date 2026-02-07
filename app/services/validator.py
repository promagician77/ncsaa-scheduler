"""
Schedule validation module for the NCSAA Basketball Scheduling System.
Validates schedules against all hard and soft constraints.
"""

from datetime import timedelta
from typing import List, Dict, Set
from collections import defaultdict

from app.models import (
    Schedule, Game, Team, SchedulingConstraint,
    ScheduleValidationResult, TeamScheduleStats, Division
)
from app.core.config import (
    MAX_GAMES_PER_7_DAYS, MAX_GAMES_PER_14_DAYS,
    MAX_DOUBLEHEADERS_PER_SEASON, DOUBLEHEADER_BREAK_MINUTES,
    PRIORITY_WEIGHTS, WEEKNIGHT_START_TIME, SATURDAY_START_TIME,
    ES_K1_REC_OFFICIALS, EIGHTH_GAME_CUTOFF_DATE
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
        self._check_same_school_conflicts(schedule, result)  # NEW: Check for same school conflicts (simultaneous play)
        self._check_same_school_matchups(schedule, result)  # NEW: Rule 23 - Same-school teams never play each other
        self._check_duplicate_matchups(schedule, result)  # NEW: Check for excessive rematches
        self._check_games_per_team(schedule, result)  # NEW: Rule 22 - Each team plays exactly 8 games
        self._check_team_game_frequency(schedule, result)
        self._check_doubleheader_limits(schedule, result)
        self._check_eighth_game_date(schedule, result)  # NEW: Check 8th game date restriction (Rule 17)
        self._check_saturday_facility_consolidation(schedule, result)  # NEW: Rule 20 facility consolidation
        self._check_do_not_play_constraints(schedule, result)
        self._check_facility_availability(schedule, result)
        self._check_home_away_balance(schedule, result)
        self._check_rival_matchups(schedule, result)
        self._check_k1_rec_requirements(schedule, result)  # NEW: Check ES K-1 REC special requirements
        self._check_k1_cluster_restriction(schedule, result)  # NEW: Rule 21 - K-1 cluster-only scheduling
        self._check_rec_division_grouping(schedule, result)  # NEW: Check REC divisions are grouped together
        
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
    
    def _check_games_per_team(self, schedule: Schedule, result: ScheduleValidationResult):
        """
        Check if each team plays exactly 8 games (Rule 22).
        
        Rule 22: Each team plays 8 games.
        This is a fundamental requirement of the league.
        """
        from app.core.config import GAMES_PER_TEAM
        
        print(f"\nValidating games per team (Rule 22: exactly {GAMES_PER_TEAM} games)...")
        
        # Get all unique teams
        teams = set()
        for game in schedule.games:
            teams.add(game.home_team)
            teams.add(game.away_team)
        
        insufficient = 0
        excessive = 0
        
        for team in teams:
            team_games = schedule.get_team_games(team)
            game_count = len(team_games)
            
            if game_count < GAMES_PER_TEAM:
                insufficient += 1
                constraint = SchedulingConstraint(
                    constraint_type="insufficient_games",
                    severity="hard",
                    description=f"{team.id} has only {game_count} games (requires {GAMES_PER_TEAM})",
                    affected_teams=[team],
                    affected_games=team_games,
                    penalty_score=1000.0
                )
                result.add_violation(constraint)
            
            elif game_count > GAMES_PER_TEAM:
                excessive += 1
                constraint = SchedulingConstraint(
                    constraint_type="excessive_games",
                    severity="hard",
                    description=f"{team.id} has {game_count} games (requires {GAMES_PER_TEAM})",
                    affected_teams=[team],
                    affected_games=team_games,
                    penalty_score=1000.0
                )
                result.add_violation(constraint)
        
        if insufficient > 0:
            print(f"  ❌ {insufficient} teams have < {GAMES_PER_TEAM} games")
        if excessive > 0:
            print(f"  ❌ {excessive} teams have > {GAMES_PER_TEAM} games")
        if insufficient == 0 and excessive == 0:
            print(f"  ✅ All teams have exactly {GAMES_PER_TEAM} games")
    
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
        """Check if teams exceed doubleheader limits and have proper breaks."""
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
                        
                        # Rule 14: Check if doubleheader has sufficient break (>= 60 minutes)
                        if gap_minutes < DOUBLEHEADER_BREAK_MINUTES:
                            constraint = SchedulingConstraint(
                                constraint_type="insufficient_doubleheader_break",
                                severity="hard",
                                description=f"{team.id} has doubleheader with only {gap_minutes} min break (requires {DOUBLEHEADER_BREAK_MINUTES} min) on {game1.time_slot.date}",
                                affected_teams=[team],
                                affected_games=[game1, game2],
                                penalty_score=350.0
                            )
                            result.add_violation(constraint)
            
            # Rule 13: Check max doubleheaders per season
            if doubleheader_count > MAX_DOUBLEHEADERS_PER_SEASON:
                constraint = SchedulingConstraint(
                    constraint_type="too_many_doubleheaders",
                    severity="hard",
                    description=f"{team.id} has {doubleheader_count} doubleheaders (max {MAX_DOUBLEHEADERS_PER_SEASON})",
                    affected_teams=[team],
                    penalty_score=400.0
                )
                result.add_violation(constraint)
    
    def _check_eighth_game_date(self, schedule: Schedule, result: ScheduleValidationResult):
        """Check if any team has their 8th game before February 21 (Rule 17)."""
        from datetime import datetime
        
        cutoff_date = datetime.strptime(EIGHTH_GAME_CUTOFF_DATE, "%Y-%m-%d").date()
        
        # Get all unique teams
        teams = set()
        for game in schedule.games:
            teams.add(game.home_team)
            teams.add(game.away_team)
        
        for team in teams:
            # Get all games for this team, sorted by date
            team_games = sorted(schedule.get_team_games(team), 
                              key=lambda g: g.time_slot.date)
            
            # Check if team has 8 games (full season)
            if len(team_games) >= 8:
                # Get the 8th game (index 7)
                eighth_game = team_games[7]
                
                # Check if 8th game is before cutoff date
                if eighth_game.time_slot.date < cutoff_date:
                    constraint = SchedulingConstraint(
                        constraint_type="eighth_game_too_early",
                        severity="hard",
                        description=f"{team.id} has 8th game on {eighth_game.time_slot.date} (must be on or after {cutoff_date})",
                        affected_teams=[team],
                        affected_games=[eighth_game],
                        penalty_score=350.0
                    )
                    result.add_violation(constraint)
    
    def _check_saturday_facility_consolidation(self, schedule: Schedule, result: ScheduleValidationResult):
        """Check if Saturday games are consolidated to fewer facilities (Rule 20)."""
        from app.core.config import SATURDAY_TARGET_FACILITIES
        from collections import defaultdict
        
        # Group games by Saturday date
        saturday_games = defaultdict(list)
        for game in schedule.games:
            if game.time_slot.date.weekday() == 5:  # Saturday
                saturday_games[game.time_slot.date].append(game)
        
        # Check facility spread for each Saturday
        for saturday_date, games in saturday_games.items():
            facilities_used = set(g.time_slot.facility.name for g in games)
            num_facilities = len(facilities_used)
            
            # Soft constraint: Should use ≤target facilities (typically 4)
            if num_facilities > SATURDAY_TARGET_FACILITIES:
                # Calculate utilization per facility
                facility_game_count = defaultdict(int)
                for game in games:
                    facility_game_count[game.time_slot.facility.name] += 1
                
                facility_summary = ", ".join(
                    f"{name}: {count} games" for name, count in sorted(facility_game_count.items(), key=lambda x: -x[1])
                )
                
                constraint = SchedulingConstraint(
                    constraint_type="excessive_saturday_facility_spread",
                    severity="soft",
                    description=f"Saturday {saturday_date} uses {num_facilities} facilities (target: ≤{SATURDAY_TARGET_FACILITIES}) - {facility_summary}",
                    affected_teams=[],
                    affected_games=games,
                    penalty_score=30.0 * (num_facilities - SATURDAY_TARGET_FACILITIES)
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
    
    def _check_same_school_matchups(self, schedule: Schedule, result: ScheduleValidationResult):
        """
        Check that teams from the same school never play each other (Rule 23).
        
        Rule 23: Some schools have 2 teams in a division. They should never play each other.
        This is a CRITICAL hard constraint - same-school teams should NEVER be matched.
        """
        print("\nValidating same-school matchups (Rule 23: no same-school games)...")
        
        violations = 0
        
        for game in schedule.games:
            # Check if both teams from same school
            if game.home_team.school == game.away_team.school:
                violations += 1
                constraint = SchedulingConstraint(
                    constraint_type="same_school_matchup",
                    severity="hard",
                    description=f"Same-school matchup: {game.home_team.id} vs {game.away_team.id} (both from {game.home_team.school.name})",
                    affected_teams=[game.home_team, game.away_team],
                    affected_games=[game],
                    penalty_score=2000.0  # Very high penalty - this should NEVER happen
                )
                result.add_violation(constraint)
        
        if violations > 0:
            print(f"  ❌ Found {violations} same-school matchups (CRITICAL ERROR)")
        else:
            print(f"  ✅ No same-school teams playing each other")
    
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
    
    def _check_k1_rec_requirements(self, schedule: Schedule, result: ScheduleValidationResult):
        """
        Validate ES K-1 REC special requirements (Rule 9).
        
        Rule 9 Requirements:
        1. K-1 games use 1 official (not 2)
        2. K-1 games need 8ft rim facilities OR own site at start of day
        3. LVBC K-1 games must be on Court 5 only
        4. Non-K-1 games cannot use 8ft rim facilities
        """
        print("\nValidating ES K-1 REC requirements...")
        
        for game in schedule.games:
            # Check 1: K-1 games should have 1 official
            if game.division == Division.ES_K1_REC:
                if game.officials_count != ES_K1_REC_OFFICIALS:
                    constraint = SchedulingConstraint(
                        constraint_type="k1_officials_count",
                        severity="hard",
                        description=f"K-1 game {game.id} has {game.officials_count} officials (should be {ES_K1_REC_OFFICIALS})",
                        affected_games=[game],
                        penalty_score=100.0
                    )
                    result.add_violation(constraint)
                
                # Check 2: K-1 at non-8ft facilities must be at own site at start of day
                if not game.time_slot.facility.has_8ft_rims:
                    home_school_name = game.home_team.school.name
                    away_school_name = game.away_team.school.name
                    facility_name = game.time_slot.facility.name.lower()
                    
                    # Check if facility belongs to either school
                    home_owns = self._facility_belongs_to_school(facility_name, home_school_name)
                    away_owns = self._facility_belongs_to_school(facility_name, away_school_name)
                    
                    if not (home_owns or away_owns):
                        constraint = SchedulingConstraint(
                            constraint_type="k1_facility_requirement",
                            severity="hard",
                            description=f"K-1 game {game.id} at non-8ft facility {game.time_slot.facility.name} (not owned by playing schools)",
                            affected_games=[game],
                            penalty_score=500.0
                        )
                        result.add_violation(constraint)
                    else:
                        # Check if it's at start of day
                        is_start = self._is_start_of_day(game.time_slot.date, game.time_slot.start_time)
                        if not is_start:
                            owner = home_school_name if home_owns else away_school_name
                            constraint = SchedulingConstraint(
                                constraint_type="k1_start_of_day",
                                severity="hard",
                                description=f"K-1 game {game.id} at {owner}'s facility but not at start of day ({game.time_slot.start_time})",
                                affected_games=[game],
                                penalty_score=300.0
                            )
                            result.add_violation(constraint)
                
                # Check 3: LVBC K-1 games must be on Court 5
                if 'las vegas basketball center' in game.time_slot.facility.name.lower() or 'lvbc' in game.time_slot.facility.name.lower():
                    if game.time_slot.court_number != 5:
                        constraint = SchedulingConstraint(
                            constraint_type="k1_lvbc_court_5",
                            severity="hard",
                            description=f"K-1 game {game.id} at LVBC on Court {game.time_slot.court_number} (must be Court 5)",
                            affected_games=[game],
                            penalty_score=400.0
                        )
                        result.add_violation(constraint)
            
            # Check 4: Non-K-1 games should not be on 8ft facilities
            else:
                if game.time_slot.facility.has_8ft_rims:
                    constraint = SchedulingConstraint(
                        constraint_type="non_k1_on_8ft_facility",
                        severity="hard",
                        description=f"Non-K-1 game {game.id} ({game.division.value}) scheduled at 8ft facility {game.time_slot.facility.name}",
                        affected_games=[game],
                        penalty_score=500.0
                    )
                    result.add_violation(constraint)
    
    def _check_k1_cluster_restriction(self, schedule: Schedule, result: ScheduleValidationResult):
        """
        Check if ES K-1 REC teams only play within their cluster (Rule 21).
        
        Rule 21: ES K-1 REC teams should only play in their cluster/region.
        Tiers do not apply to this division.
        """
        print("\nValidating ES K-1 REC cluster restrictions (Rule 21)...")
        
        k1_violations = 0
        k1_missing_cluster = 0
        
        for game in schedule.games:
            if game.division == Division.ES_K1_REC:
                home_cluster = game.home_team.cluster
                away_cluster = game.away_team.cluster
                
                # Check if both teams have cluster assigned
                if home_cluster and away_cluster:
                    # Check if different clusters (VIOLATION)
                    if home_cluster != away_cluster:
                        k1_violations += 1
                        constraint = SchedulingConstraint(
                            constraint_type="k1_cross_cluster_violation",
                            severity="hard",
                            description=f"K-1 game {game.id} crosses clusters: {game.home_team.id} ({home_cluster.value}) vs {game.away_team.id} ({away_cluster.value})",
                            affected_teams=[game.home_team, game.away_team],
                            affected_games=[game],
                            penalty_score=500.0
                        )
                        result.add_violation(constraint)
                # Check if either team missing cluster assignment (DATA ISSUE)
                elif not home_cluster or not away_cluster:
                    k1_missing_cluster += 1
                    missing_team = game.home_team if not home_cluster else game.away_team
                    constraint = SchedulingConstraint(
                        constraint_type="k1_missing_cluster",
                        severity="soft",
                        description=f"K-1 game {game.id}: {missing_team.id} has no cluster assigned",
                        affected_teams=[missing_team],
                        affected_games=[game],
                        penalty_score=50.0
                    )
                    result.add_violation(constraint)
        
        if k1_violations > 0:
            print(f"  ❌ Found {k1_violations} K-1 cross-cluster violations")
        else:
            print(f"  ✅ All K-1 games within same cluster")
        
        if k1_missing_cluster > 0:
            print(f"  ⚠️  Found {k1_missing_cluster} K-1 teams missing cluster assignment")
    
    def _facility_belongs_to_school(self, facility_name: str, school_name: str) -> bool:
        """Check if a facility belongs to a school based on name matching."""
        facility_lower = facility_name.lower()
        school_lower = school_name.lower()
        
        # Handle common misspellings
        facility_lower = facility_lower.replace('pincrest', 'pinecrest')
        school_lower = school_lower.replace('pincrest', 'pinecrest')
        
        # Remove color suffixes from school name
        color_suffixes = [' blue', ' black', ' white', ' red', ' gold', ' silver', 
                         ' navy', ' green', ' purple', ' orange', ' yellow']
        school_base = school_lower
        for suffix in color_suffixes:
            if school_base.endswith(suffix):
                school_base = school_base[:-len(suffix)].strip()
                break
        
        # Remove trailing tier numbers (e.g., "Doral 1A" -> "Doral")
        import re
        school_base = re.sub(r'\s+\d+[a-z]?$', '', school_base).strip()
        
        # Check if school name is in facility name
        if school_base in facility_lower or school_lower in facility_lower:
            return True
        
        return False
    
    def _is_start_of_day(self, game_date, start_time) -> bool:
        """Check if the game is at the start of the day."""
        day_of_week = game_date.weekday()
        
        if day_of_week < 5:  # Weeknight
            return start_time == WEEKNIGHT_START_TIME
        elif day_of_week == 5:  # Saturday
            return start_time == SATURDAY_START_TIME
        else:
            return False
    
    def _check_rec_division_grouping(self, schedule: Schedule, result: ScheduleValidationResult):
        """
        Validate that REC divisions are grouped together (Rule 11).
        
        Rule 11: "Rec is the only divisions that need to be grouped together"
        Competitive divisions can be in any order, but REC divisions (K-1 and 2-3)
        should be scheduled consecutively.
        """
        print("\nValidating REC division grouping (Rule 11)...")
        
        # Group games by school matchup (same facility, date, consecutive times)
        from collections import defaultdict
        matchup_games = defaultdict(list)
        
        for game in schedule.games:
            # Create key: (date, facility, school_a, school_b)
            schools = tuple(sorted([game.home_team.school.name, game.away_team.school.name]))
            key = (game.time_slot.date, game.time_slot.facility.name, schools[0], schools[1])
            matchup_games[key].append(game)
        
        # Check each matchup for REC division grouping
        for matchup_key, games in matchup_games.items():
            if len(games) < 2:
                continue  # Single game, no grouping needed
            
            # Sort games by time
            sorted_games = sorted(games, key=lambda g: g.time_slot.start_time)
            
            # Find REC divisions and their positions
            rec_positions = []
            comp_positions = []
            
            for i, game in enumerate(sorted_games):
                if game.division == Division.ES_K1_REC or game.division == Division.ES_23_REC:
                    rec_positions.append(i)
                else:
                    comp_positions.append(i)
            
            # If we have both REC and competitive divisions, check grouping
            if rec_positions and comp_positions:
                # Check if REC divisions are consecutive
                if len(rec_positions) > 1:
                    # All REC games should be consecutive (no gaps)
                    expected_consecutive = list(range(rec_positions[0], rec_positions[0] + len(rec_positions)))
                    
                    if rec_positions != expected_consecutive:
                        # REC divisions are not grouped together
                        rec_games = [sorted_games[i] for i in rec_positions]
                        constraint = SchedulingConstraint(
                            constraint_type="rec_division_grouping",
                            severity="soft",  # Soft constraint - preference, not hard rule
                            description=f"REC divisions not grouped together at {matchup_key[1]} on {matchup_key[0]}",
                            affected_games=rec_games,
                            penalty_score=30.0
                        )
                        result.add_violation(constraint)
                
                # Check if REC divisions are at start or end (best practice)
                if rec_positions:
                    all_at_start = all(i < len(comp_positions) or i == min(rec_positions + comp_positions) for i in rec_positions)
                    all_at_end = all(i > max(comp_positions) for i in rec_positions) if comp_positions else True
                    
                    if not (all_at_start or all_at_end):
                        # REC divisions are in the middle (not ideal)
                        rec_games = [sorted_games[i] for i in rec_positions]
                        constraint = SchedulingConstraint(
                            constraint_type="rec_division_position",
                            severity="soft",  # Soft constraint - best practice
                            description=f"REC divisions in middle of schedule (prefer start/end) at {matchup_key[1]} on {matchup_key[0]}",
                            affected_games=rec_games,
                            penalty_score=10.0
                        )
                        result.add_violation(constraint)