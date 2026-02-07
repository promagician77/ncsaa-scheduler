"""
Schedule optimizer using constraint satisfaction and optimization algorithms.
Uses Google OR-Tools CP-SAT solver for constraint programming.
"""

from ortools.sat.python import cp_model
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
import itertools

from app.models import (
    Team, Facility, Game, TimeSlot, Division, Schedule,
    SchedulingConstraint, ScheduleValidationResult
)
from app.core.config import (
    SEASON_START_DATE, SEASON_END_DATE, US_HOLIDAYS,
    WEEKNIGHT_START_TIME, WEEKNIGHT_END_TIME,
    SATURDAY_START_TIME, SATURDAY_END_TIME,
    GAME_DURATION_MINUTES, WEEKNIGHT_SLOTS,
    MAX_GAMES_PER_7_DAYS, MAX_GAMES_PER_14_DAYS,
    MAX_DOUBLEHEADERS_PER_SEASON, DOUBLEHEADER_BREAK_MINUTES,
    NO_GAMES_ON_SUNDAY, REC_DIVISIONS, ES_K1_REC_PRIORITY_SITES,
    PRIORITY_WEIGHTS
)


class ScheduleOptimizer:
    """
    Optimizes basketball game schedules using constraint programming.
    Uses Google OR-Tools CP-SAT solver for finding optimal solutions.
    """
    
    def __init__(self, teams: List[Team], facilities: List[Facility], rules: Dict):
        """
        Initialize the scheduler with teams, facilities, and rules.
        
        Args:
            teams: List of all teams to schedule
            facilities: List of available facilities
            rules: Dictionary of scheduling rules from config
        """
        self.teams = teams
        self.facilities = facilities
        self.rules = rules
        
        # Parse season dates
        self.season_start = self._parse_date(rules.get('season_start', SEASON_START_DATE))
        self.season_end = self._parse_date(rules.get('season_end', SEASON_END_DATE))
        
        # Holidays and blackout dates
        self.holidays = set(rules.get('holidays', []))
        for holiday_str in US_HOLIDAYS:
            self.holidays.add(self._parse_date(holiday_str))
        
        # Group teams by division
        self.teams_by_division = self._group_teams_by_division()
        
        # Generate all possible time slots
        self.time_slots = self._generate_time_slots()
        
        print(f"Scheduler initialized:")
        print(f"  Season: {self.season_start} to {self.season_end}")
        print(f"  Teams: {len(self.teams)}")
        print(f"  Facilities: {len(self.facilities)}")
        print(f"  Time slots: {len(self.time_slots)}")
    
    def _parse_date(self, date_input) -> date:
        """Parse a date from string or date object."""
        if isinstance(date_input, date):
            return date_input
        if isinstance(date_input, str):
            return datetime.strptime(date_input, '%Y-%m-%d').date()
        return date_input
    
    def _group_teams_by_division(self) -> Dict[Division, List[Team]]:
        """Group teams by their division."""
        groups = defaultdict(list)
        for team in self.teams:
            groups[team.division].append(team)
        return dict(groups)
    
    def _is_valid_game_date(self, game_date: date) -> bool:
        """Check if a date is valid for scheduling games."""
        # Check if within season
        if game_date < self.season_start or game_date > self.season_end:
            return False
        
        # Check if holiday
        if game_date in self.holidays:
            return False
        
        # Check if Sunday (no games on Sunday)
        if NO_GAMES_ON_SUNDAY and game_date.weekday() == 6:
            return False
        
        return True
    
    def _generate_time_slots(self) -> List[TimeSlot]:
        """
        Generate all possible time slots for the season.
        Creates slots for weeknights (Mon-Fri) and Saturdays.
        """
        slots = []
        current_date = self.season_start
        
        while current_date <= self.season_end:
            if not self._is_valid_game_date(current_date):
                current_date += timedelta(days=1)
                continue
            
            day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday
            
            # Weeknight slots (Monday-Friday)
            if day_of_week < 5:
                start_time = WEEKNIGHT_START_TIME
                for slot_num in range(WEEKNIGHT_SLOTS):
                    slot_start = datetime.combine(date.min, start_time) + timedelta(minutes=slot_num * GAME_DURATION_MINUTES)
                    slot_end = slot_start + timedelta(minutes=GAME_DURATION_MINUTES)
                    
                    # Check if within allowed time window
                    if slot_end.time() <= WEEKNIGHT_END_TIME:
                        for facility in self.facilities:
                            if facility.is_available(current_date):
                                for court in range(1, facility.max_courts + 1):
                                    slots.append(TimeSlot(
                                        date=current_date,
                                        start_time=slot_start.time(),
                                        end_time=slot_end.time(),
                                        facility=facility,
                                        court_number=court
                                    ))
            
            # Saturday slots
            elif day_of_week == 5:
                current_time = datetime.combine(date.min, SATURDAY_START_TIME)
                end_datetime = datetime.combine(date.min, SATURDAY_END_TIME)
                
                while current_time + timedelta(minutes=GAME_DURATION_MINUTES) <= end_datetime:
                    slot_start = current_time
                    slot_end = current_time + timedelta(minutes=GAME_DURATION_MINUTES)
                    
                    for facility in self.facilities:
                        if facility.is_available(current_date):
                            for court in range(1, facility.max_courts + 1):
                                slots.append(TimeSlot(
                                    date=current_date,
                                    start_time=slot_start.time(),
                                    end_time=slot_end.time(),
                                    facility=facility,
                                    court_number=court
                                ))
                    
                    current_time += timedelta(minutes=GAME_DURATION_MINUTES)
            
            current_date += timedelta(days=1)
        
        return slots
    
    def _calculate_matchup_score(self, team1: Team, team2: Team) -> int:
        """
        Calculate a preference score for a matchup (higher is better).
        Considers tier matching, geographic clustering, etc.
        
        CRITICAL: Teams from the same school should NEVER play each other (Rule #23)
        """
        # CRITICAL: Teams from same school CANNOT play each other
        if team1.school == team2.school:
            return -999999  # Extremely negative score to prevent this matchup
        
        score = 0
        
        # Same tier is preferred
        if team1.tier and team2.tier and team1.tier == team2.tier:
            score += PRIORITY_WEIGHTS['tier_matching']
        
        # Same geographic cluster is preferred
        if team1.cluster and team2.cluster and team1.cluster == team2.cluster:
            score += PRIORITY_WEIGHTS['geographic_cluster']
        
        # Same coach is preferred (but only if different schools)
        if team1.coach_name and team2.coach_name and team1.coach_name == team2.coach_name:
            score += PRIORITY_WEIGHTS['cluster_same_coach']
        
        # Rivals should play each other
        if team2.id in team1.rivals:
            score += PRIORITY_WEIGHTS['respect_rivals']
        
        return score
    
    def optimize_schedule(self) -> Schedule:
        """
        Generate an optimized schedule using constraint programming.
        This is the main entry point for schedule generation.
        """
        print("\n" + "=" * 60)
        print("Starting schedule optimization...")
        print("=" * 60)
        
        schedule = Schedule(
            season_start=self.season_start,
            season_end=self.season_end
        )
        
        # CRITICAL: Track school time slots across ALL divisions to prevent same-school conflicts
        self.global_school_time_slots = defaultdict(set)
        
        # CRITICAL: Track facility/court usage across ALL divisions to prevent double-booking
        # Key: (date, start_time, facility_name, court_number), Value: True if used
        self.global_used_slots = set()
        
        # Schedule each division separately
        for division, division_teams in self.teams_by_division.items():
            print(f"\nScheduling division: {division.value}")
            print(f"  Teams: {len(division_teams)}")
            
            if len(division_teams) < 2:
                print(f"  Skipping - not enough teams")
                continue
            
            # For larger divisions (30+ teams), try CP-SAT first for better quality
            # For smaller divisions, use greedy algorithm (faster, still good quality)
            if len(division_teams) >= 30:
                print(f"  Using CP-SAT solver (large division, 30s timeout)...")
                division_games = self._schedule_division(division, division_teams)
                # If CP-SAT fails or produces incomplete schedule, use greedy
                team_counts = defaultdict(int)
                for game in division_games:
                    team_counts[game.home_team.id] += 1
                    team_counts[game.away_team.id] += 1
                teams_under_8 = [t for t in division_teams if team_counts[t.id] < 8]
                if teams_under_8:
                    print(f"  CP-SAT incomplete ({len(teams_under_8)} teams < 8 games), switching to greedy algorithm...")
                    division_games = self._greedy_schedule_division(division, division_teams)
            else:
                print(f"  Using optimized greedy algorithm...")
                division_games = self._greedy_schedule_division(division, division_teams)
            
            for game in division_games:
                schedule.add_game(game)
            
            print(f"  Generated {len(division_games)} games")
        
        print("\n" + "=" * 60)
        print(f"Schedule optimization complete: {len(schedule.games)} total games")
        print("=" * 60)
        
        return schedule
    
    def _schedule_division(self, division: Division, teams: List[Team]) -> List[Game]:
        """
        Schedule games for a single division using CP-SAT solver.
        
        Args:
            division: The division to schedule
            teams: List of teams in this division
            
        Returns:
            List of scheduled games
        """
        model = cp_model.CpModel()
        
        # Create variables for each possible matchup and time slot
        # game_vars[team1_idx][team2_idx][slot_idx] = BoolVar
        game_vars = {}
        matchup_scores = {}
        
        num_teams = len(teams)
        
        # Filter time slots to exclude:
        # 1. Facility/court slots already used by other divisions
        # 2. Time slots where schools from this division are already playing
        usable_slot_indices = []
        schools_in_division = set(team.school.name for team in teams)
        
        for slot_idx, slot in enumerate(self.time_slots):
            # Check if this specific facility/court slot is already used
            slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
            if hasattr(self, 'global_used_slots') and slot_key in self.global_used_slots:
                continue  # This facility/court is already in use at this time
            
            # Check if any school from this division is already playing at this time
            time_slot_key = (slot.date, slot.start_time)
            school_conflict = False
            if hasattr(self, 'global_school_time_slots'):
                for school_name in schools_in_division:
                    if time_slot_key in self.global_school_time_slots[school_name]:
                        school_conflict = True
                        break
            
            if not school_conflict:
                usable_slot_indices.append(slot_idx)
        
        num_slots = len(usable_slot_indices)
        
        # Generate all possible matchups
        matchups = []
        for i in range(num_teams):
            for j in range(i + 1, num_teams):
                team1, team2 = teams[i], teams[j]
                
                # CRITICAL: Skip same-school matchups (Rule #23) - HARD constraint
                if team1.school == team2.school:
                    continue
                
                # Check do-not-play constraint
                if team2.id in team1.do_not_play or team1.id in team2.do_not_play:
                    continue
                
                matchups.append((i, j))
                matchup_scores[(i, j)] = self._calculate_matchup_score(team1, team2)
        
        # Create decision variables
        # For each matchup, for each usable slot, create a variable indicating if game is scheduled
        for (i, j) in matchups:
            game_vars[(i, j)] = {}
            for idx, slot_idx in enumerate(usable_slot_indices):
                var_name = f'game_t{i}_t{j}_s{idx}'
                game_vars[(i, j)][idx] = model.NewBoolVar(var_name)
        
        # CONSTRAINT 1: Each team plays exactly 8 games (rule requirement)
        target_games_per_team = 8  # All teams must play exactly 8 games
        
        for team_idx in range(num_teams):
            team_games = []
            for (i, j) in matchups:
                if i == team_idx or j == team_idx:
                    for idx in range(num_slots):
                        if idx in game_vars[(i, j)]:
                            team_games.append(game_vars[(i, j)][idx])
            
            # Each team must play exactly 8 games
            if team_games:
                model.Add(sum(team_games) == target_games_per_team)
        
        # CONSTRAINT 2: Each matchup happens at most once
        for (i, j) in matchups:
            model.Add(sum(game_vars[(i, j)][idx] for idx in range(num_slots) if idx in game_vars[(i, j)]) <= 1)
        
        # CONSTRAINT 3: No team plays multiple games at the same time
        for idx in range(num_slots):
            for team_idx in range(num_teams):
                games_at_slot = []
                for (i, j) in matchups:
                    if (i == team_idx or j == team_idx) and idx in game_vars[(i, j)]:
                        games_at_slot.append(game_vars[(i, j)][idx])
                
                if games_at_slot:
                    model.Add(sum(games_at_slot) <= 1)
        
        # CONSTRAINT 4: Respect max games per 7 days
        for team_idx in range(num_teams):
            # Group usable slots by week
            slots_by_week = defaultdict(list)
            for idx, slot_idx in enumerate(usable_slot_indices):
                slot = self.time_slots[slot_idx]
                week_num = (slot.date - self.season_start).days // 7
                slots_by_week[week_num].append(idx)
            
            for week_slot_indices in slots_by_week.values():
                games_in_week = []
                for (i, j) in matchups:
                    if i == team_idx or j == team_idx:
                        for idx in week_slot_indices:
                            if idx in game_vars[(i, j)]:
                                games_in_week.append(game_vars[(i, j)][idx])
                
                if games_in_week:
                    model.Add(sum(games_in_week) <= MAX_GAMES_PER_7_DAYS)
        
        # CONSTRAINT 5: Only one game per time slot per facility/court
        for idx in range(num_slots):
            games_at_slot = []
            for (i, j) in matchups:
                if idx in game_vars[(i, j)]:
                    games_at_slot.append(game_vars[(i, j)][idx])
            
            if games_at_slot:
                # Allow multiple games at same time if different courts
                model.Add(sum(games_at_slot) <= 1)
        
        # OBJECTIVE: Maximize matchup quality scores
        objective_terms = []
        for (i, j) in matchups:
            score = matchup_scores[(i, j)]
            for idx in range(num_slots):
                if idx in game_vars[(i, j)]:
                    objective_terms.append(game_vars[(i, j)][idx] * score)
        
        if objective_terms:
            model.Maximize(sum(objective_terms))
        
        # Solve the model
        # Optimal timeout: 30 seconds per division provides good balance
        # - Too short (<15s): May miss optimal solutions, but fast
        # - Too long (>60s): Better solutions, but slow for large divisions
        # - 30s: Good balance for most divisions, finds good solutions
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0  # 30 seconds per division - optimal balance
        solver.parameters.num_search_workers = 4  # Use parallel workers
        solver.parameters.log_search_progress = False
        
        print(f"  Solving CP-SAT model (30s timeout)...")
        status = solver.Solve(model)
        
        # Extract solution
        games = []
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"  Solution found (status: {solver.StatusName(status)})")
            
            game_id = 0
            for (i, j) in matchups:
                for idx in range(num_slots):
                    if idx in game_vars[(i, j)] and solver.Value(game_vars[(i, j)][idx]):
                        team1 = teams[i]
                        team2 = teams[j]
                        actual_slot_idx = usable_slot_indices[idx]
                        slot = self.time_slots[actual_slot_idx]
                        
                        # Determine home/away
                        # Prefer team1's home facility if available
                        home_team = team1
                        away_team = team2
                        
                        if team2.home_facility and team2.home_facility == slot.facility.name:
                            home_team = team2
                            away_team = team1
                        
                        game = Game(
                            id=f"{division.value}_{game_id}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=division
                        )
                        
                        games.append(game)
                        
                        # Update global tracking to prevent cross-division conflicts
                        time_slot_key = (slot.date, slot.start_time)
                        slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        
                        if hasattr(self, 'global_school_time_slots'):
                            self.global_school_time_slots[home_team.school.name].add(time_slot_key)
                            self.global_school_time_slots[away_team.school.name].add(time_slot_key)
                        
                        if hasattr(self, 'global_used_slots'):
                            self.global_used_slots.add(slot_key)
                        
                        game_id += 1
        else:
            print(f"  No solution found (status: {solver.StatusName(status)})")
            # Fallback to greedy algorithm
            games = self._greedy_schedule_division(division, teams)
        
        return games
    
    def _greedy_schedule_division(self, division: Division, teams: List[Team]) -> List[Game]:
        """
        Optimized greedy algorithm for scheduling.
        Schedules games one by one, respecting hard constraints.
        Ensures all teams play exactly 8 games.
        """
        games = []
        used_slots = set()  # Local tracking for this division
        team_games_count = defaultdict(int)
        team_last_game_date = {}
        matchups_used = set()
        rematches_used = set()  # Track rematches separately
        matchup_frequency = defaultdict(int)  # Track how many times each matchup is scheduled
        
        # CRITICAL: Track which time slots each team is using to prevent double-booking
        team_time_slots = defaultdict(set)  # Key: team.id, Value: set of (date, start_time) tuples
        
        # Use global school tracking to prevent same-school conflicts across ALL divisions
        if not hasattr(self, 'global_school_time_slots'):
            self.global_school_time_slots = defaultdict(set)
        school_time_slots = self.global_school_time_slots  # Reference to global tracking
        
        # Use global facility/court tracking to prevent double-booking across divisions
        if not hasattr(self, 'global_used_slots'):
            self.global_used_slots = set()
        global_used_slots = self.global_used_slots  # Reference to global tracking
        
        # Pre-filter time slots by division requirements and global availability
        usable_slots = []
        for slot in self.time_slots:
            # ES K-1 REC needs 8ft rims
            if division == Division.ES_K1_REC and not slot.facility.has_8ft_rims:
                continue
            # Check facility availability
            if not slot.facility.is_available(slot.date):
                continue
            
            # CRITICAL: Check if this facility/court is already used by another division
            slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
            if slot_key in global_used_slots:
                continue  # Already used by another division
            
            # Check if schools from this division are already playing at this time
            time_slot_key = (slot.date, slot.start_time)
            schools_in_division = set(team.school.name for team in teams)
            school_conflict = False
            for school_name in schools_in_division:
                if time_slot_key in school_time_slots[school_name]:
                    school_conflict = True
                    break
            
            if not school_conflict:
                usable_slots.append(slot)
        
        # Sort slots by date and time for better scheduling
        usable_slots.sort(key=lambda s: (s.date, s.start_time))
        
        print(f"  Using {len(usable_slots)} filtered slots (from {len(self.time_slots)} total)")
        
        # Generate all possible matchups sorted by preference
        matchups = []
        for i, team1 in enumerate(teams):
            for j, team2 in enumerate(teams[i + 1:], start=i + 1):
                # CRITICAL: Skip same-school matchups (Rule #23)
                if team1.school == team2.school:
                    continue
                
                # Skip do-not-play
                if team2.id in team1.do_not_play or team1.id in team2.do_not_play:
                    continue
                
                score = self._calculate_matchup_score(team1, team2)
                matchups.append((score, team1, team2))
        
        # Sort by score (highest first)
        matchups.sort(reverse=True, key=lambda x: x[0])
        
        # TARGET: All teams should play exactly 8 games (rule requirement)
        target_games = 8
        
        # FIRST PASS: Schedule matchups prioritizing high-quality matchups
        for score, team1, team2 in matchups:
            # Skip if either team already has 8 games (strict limit)
            if team_games_count[team1.id] >= target_games or team_games_count[team2.id] >= target_games:
                continue
            
            # Check if matchup already scheduled
            matchup_key = tuple(sorted([team1.id, team2.id]))
            if matchup_key in matchups_used:
                continue
            
            # Find a suitable time slot (use filtered slots)
            for slot in usable_slots:
                slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                
                # Check local usage (within this division)
                if slot_key in used_slots:
                    continue
                
                # Double-check global usage (should already be filtered, but be safe)
                if slot_key in global_used_slots:
                    continue
                
                # Check if teams can play on this date/time
                can_play = True
                time_slot_key = (slot.date, slot.start_time)
                
                # CRITICAL: Check if either team is already playing at this exact time (prevents double-booking)
                for team in [team1, team2]:
                    if time_slot_key in team_time_slots[team.id]:
                        can_play = False
                        break
                
                if not can_play:
                    continue
                
                # Check if teams from same school are already playing at this time
                for team in [team1, team2]:
                    if time_slot_key in school_time_slots[team.school.name]:
                        can_play = False
                        break
                
                if not can_play:
                    continue
                
                # Check last game date (min 2 days between games)
                for team in [team1, team2]:
                    if team.id in team_last_game_date:
                        days_since = (slot.date - team_last_game_date[team.id]).days
                        if days_since < 2:
                            can_play = False
                            break
                
                if not can_play:
                    continue
                
                # Schedule the game
                home_team = team1
                away_team = team2
                
                if team2.home_facility and team2.home_facility == slot.facility.name:
                    home_team = team2
                    away_team = team1
                
                game = Game(
                    id=f"{division.value}_{len(games)}",
                    home_team=home_team,
                    away_team=away_team,
                    time_slot=slot,
                    division=division
                )
                
                games.append(game)
                used_slots.add(slot_key)
                global_used_slots.add(slot_key)  # Mark as used globally
                
                # Track that these teams are now busy at this time slot (prevents double-booking)
                team_time_slots[team1.id].add(time_slot_key)
                team_time_slots[team2.id].add(time_slot_key)
                
                # Track that these schools are now busy at this time slot
                school_time_slots[team1.school.name].add(time_slot_key)
                school_time_slots[team2.school.name].add(time_slot_key)
                
                team_games_count[team1.id] += 1
                team_games_count[team2.id] += 1
                team_last_game_date[team1.id] = slot.date
                team_last_game_date[team2.id] = slot.date
                matchups_used.add(matchup_key)
                matchup_frequency[matchup_key] += 1
                
                break
        
        # SECOND PASS: Fill remaining games for teams with less than 8 games
        # Prioritize teams with fewer games
        teams_needing_games = [
            team for team in teams 
            if team_games_count[team.id] < target_games
        ]
        
        if teams_needing_games:
            print(f"  Second pass: {len(teams_needing_games)} teams need more games")
            
            # Sort teams by number of games (fewest first) - prioritize teams most behind
            teams_needing_games.sort(key=lambda t: team_games_count[t.id])
            
            # Multiple passes to fill games - keep trying until all teams have 8 games
            max_passes = 20  # Increased to ensure all teams reach 8 games
            for pass_num in range(max_passes):
                progress_made = False
                
                # Try to schedule additional games for teams below 8
                # Prioritize teams with fewest games first
                teams_needing_games.sort(key=lambda t: (team_games_count[t.id], t.id))
                
                for team in teams_needing_games:
                    needed = target_games - team_games_count[team.id]
                    
                    if needed <= 0:
                        continue
                    
                    # Find opponents who also need games or can play more
                    # Sort opponents by: 1) also need games, 2) matchup quality
                    potential_opponents = []
                    for opponent in teams:
                        if opponent.id == team.id:
                            continue
                        
                        # CRITICAL: NEVER allow same-school matchups (Rule #23) - this is a HARD constraint
                        if team.school == opponent.school:
                            continue
                        
                        # Skip do-not-play only in first few passes
                        # In later passes, if team desperately needs games, allow do-not-play matchups
                        if pass_num < 15:
                            if opponent.id in team.do_not_play or team.id in opponent.do_not_play:
                                continue
                        
                        opponent_needs = target_games - team_games_count[opponent.id]
                        matchup_key = tuple(sorted([team.id, opponent.id]))
                        
                        # Check if we can schedule this matchup
                        is_rematch = matchup_key in matchups_used
                        rematch_key = (matchup_key, 'rematch')
                        
                        if is_rematch:
                            # STRICT LIMIT: Teams should play each other at most 2 times total
                            current_count = matchup_frequency[matchup_key]
                            if current_count >= 2:
                                # Already played twice, no more rematches
                                continue
                            
                            # Only allow 1 rematch (so max 2 games total) and only if teams really need games
                            if team_games_count[team.id] >= 6 and team_games_count[opponent.id] >= 6:
                                # Both teams have 6+ games, don't allow rematch
                                continue
                        
                        # Calculate priority: prefer opponents who also need games
                        priority = opponent_needs * 1000 + self._calculate_matchup_score(team, opponent)
                        # Penalize do-not-play matchups
                        if opponent.id in team.do_not_play or team.id in opponent.do_not_play:
                            priority -= 5000
                        potential_opponents.append((priority, opponent, matchup_key, is_rematch))
                    
                    # Sort by priority (highest first)
                    potential_opponents.sort(reverse=True, key=lambda x: x[0])
                
                # Try to schedule games with these opponents
                for priority, opponent, matchup_key, is_rematch in potential_opponents:
                    if needed <= 0:
                        break
                    
                    # Don't schedule if opponent already has 8 games (unless we're doing rematch)
                    if not is_rematch and team_games_count[opponent.id] >= target_games:
                        continue
                    
                    # Find a suitable time slot
                    scheduled = False
                    for slot in usable_slots:
                        slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        
                        # Check local and global usage
                        if slot_key in used_slots or slot_key in global_used_slots:
                            continue
                        
                        # Check if teams can play at this time
                        can_play = True
                        time_slot_key = (slot.date, slot.start_time)
                        
                        # CRITICAL: Check if either team is already playing at this exact time (prevents double-booking)
                        for t in [team, opponent]:
                            if time_slot_key in team_time_slots[t.id]:
                                can_play = False
                                break
                        
                        if not can_play:
                            continue
                        
                        # Check if teams from same school are already playing at this time
                        for t in [team, opponent]:
                            if time_slot_key in school_time_slots[t.school.name]:
                                can_play = False
                                break
                        
                        if not can_play:
                            continue
                        
                        # Progressively relax constraints based on how many games team needs and pass number
                        min_days = 2
                        
                        # Very aggressive relaxation in later passes to ensure all teams reach 8 games
                        if pass_num >= 15:
                            # In very late passes, allow same day if desperately needed
                            min_days = 0
                        elif pass_num >= 10:
                            # In later passes, allow 1 day minimum
                            min_days = 1
                        elif team_games_count[team.id] < 3:
                            # Teams with very few games: allow same day
                            min_days = 0
                        elif team_games_count[team.id] < 5:
                            # Teams with few games: allow 1 day
                            min_days = 1
                        elif team_games_count[team.id] < 7:
                            # Teams close to 8: slightly relaxed
                            min_days = 1
                        
                        if team_games_count[opponent.id] < 3:
                            min_days = 0  # Also relax for opponent if they need games badly
                        elif team_games_count[opponent.id] < 5:
                            min_days = min(min_days, 1)
                        elif pass_num >= 10:
                            min_days = min(min_days, 1)
                        
                        for t in [team, opponent]:
                            if t.id in team_last_game_date:
                                days_since = (slot.date - team_last_game_date[t.id]).days
                                if days_since < min_days:
                                    can_play = False
                                    break
                        
                        if not can_play:
                            continue
                        
                        # Schedule the game
                        home_team = team
                        away_team = opponent
                        
                        if opponent.home_facility and opponent.home_facility == slot.facility.name:
                            home_team = opponent
                            away_team = team
                        
                        game = Game(
                            id=f"{division.value}_{len(games)}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=division
                        )
                        
                        games.append(game)
                        used_slots.add(slot_key)
                        global_used_slots.add(slot_key)  # Mark as used globally
                        
                        # Track that these teams are now busy at this time slot (prevents double-booking)
                        team_time_slots[team.id].add(time_slot_key)
                        team_time_slots[opponent.id].add(time_slot_key)
                        
                        # Track that these schools are now busy at this time slot
                        school_time_slots[team.school.name].add(time_slot_key)
                        school_time_slots[opponent.school.name].add(time_slot_key)
                        
                        team_games_count[team.id] += 1
                        team_games_count[opponent.id] += 1
                        team_last_game_date[team.id] = slot.date
                        team_last_game_date[opponent.id] = slot.date
                        
                        if is_rematch:
                            rematches_used.add((matchup_key, 'rematch'))
                            matchup_frequency[matchup_key] += 1
                        else:
                            matchups_used.add(matchup_key)
                            matchup_frequency[matchup_key] += 1
                        
                        needed -= 1
                        scheduled = True
                        break
                    
                    if scheduled:
                        progress_made = True
                        if team_games_count[team.id] >= target_games:
                            break
                
                # Remove teams that reached 8 games
                teams_needing_games = [t for t in teams_needing_games if team_games_count[t.id] < target_games]
                
                if not teams_needing_games:
                    break
                
                if not progress_made:
                    # No progress made in this pass, try more aggressive approach
                    if pass_num < max_passes - 1:
                        print(f"  Pass {pass_num + 1} complete, {len(teams_needing_games)} teams still need games")
        
        # Report final game counts and attempt final desperate fill if needed
        teams_under_8 = [t for t in teams if team_games_count[t.id] < target_games]
        if teams_under_8:
            print(f"  WARNING: {len(teams_under_8)} teams still have < 8 games:")
            for team in teams_under_8[:15]:  # Show first 15
                print(f"    {team.id}: {team_games_count[team.id]} games")
            
            # Calculate how many games are needed
            total_needed = sum(target_games - team_games_count[t.id] for t in teams_under_8)
            print(f"  Total games needed: {total_needed}")
            print(f"  Available slots remaining: {len(usable_slots) - len(used_slots)}")
            
            # Final desperate attempt: allow any matchup if teams are very far behind
            print(f"  Attempting final desperate fill pass...")
            for team in teams_under_8:
                needed = target_games - team_games_count[team.id]
                if needed <= 0:
                    continue
                
                # Try ANY opponent, even do-not-play or teams with 8 games (rematch)
                for opponent in teams:
                    if opponent.id == team.id:
                        continue
                    
                    # Try to find ANY available slot
                    for slot in usable_slots:
                        slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        time_slot_key = (slot.date, slot.start_time)
                        
                        # Check local and global usage
                        if slot_key in used_slots or slot_key in global_used_slots:
                            continue
                        
                        # CRITICAL: Even in desperate pass, NEVER allow double-booking
                        if time_slot_key in team_time_slots[team.id] or time_slot_key in team_time_slots[opponent.id]:
                            continue
                        
                        # Check school conflicts
                        if time_slot_key in school_time_slots[team.school.name] or time_slot_key in school_time_slots[opponent.school.name]:
                            continue
                        
                        # IMPORTANT: Even in desperate pass, limit rematches to max 2
                        matchup_key = tuple(sorted([team.id, opponent.id]))
                        if matchup_frequency[matchup_key] >= 2:
                            continue  # Already played twice, don't allow more
                        
                        # No minimum days constraint - just schedule it to meet rule
                        game = Game(
                            id=f"{division.value}_{len(games)}",
                            home_team=team,
                            away_team=opponent,
                            time_slot=slot,
                            division=division
                        )
                        
                        games.append(game)
                        used_slots.add(slot_key)
                        global_used_slots.add(slot_key)  # Mark as used globally
                        
                        # Track time slots
                        team_time_slots[team.id].add(time_slot_key)
                        team_time_slots[opponent.id].add(time_slot_key)
                        school_time_slots[team.school.name].add(time_slot_key)
                        school_time_slots[opponent.school.name].add(time_slot_key)
                        
                        team_games_count[team.id] += 1
                        team_games_count[opponent.id] += 1
                        team_last_game_date[team.id] = slot.date
                        team_last_game_date[opponent.id] = slot.date
                        matchup_frequency[matchup_key] += 1  # Track the matchup
                        needed -= 1
                        
                        if needed <= 0:
                            break
                    
                    if team_games_count[team.id] >= target_games:
                        break
        else:
            print(f"  SUCCESS: All {len(teams)} teams have exactly 8 games!")
        
        # Final verification
        final_teams_under_8 = [t for t in teams if team_games_count[t.id] < target_games]
        if final_teams_under_8:
            print(f"  Final status: {len(final_teams_under_8)} teams still < 8 games")
            print(f"  This indicates insufficient time slots or constraint conflicts")
        else:
            print(f"  All teams have exactly 8 games - RULE SATISFIED")
        
        return games
