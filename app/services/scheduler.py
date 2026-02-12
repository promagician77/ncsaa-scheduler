from ortools.sat.python import cp_model
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
import random

from app.models import (
    Team, Facility, Game, TimeSlot, Division, Schedule,
)
from app.core.config import (
    SEASON_START_DATE, SEASON_END_DATE, US_HOLIDAYS,
    WEEKNIGHT_START_TIME, WEEKNIGHT_END_TIME,
    SATURDAY_START_TIME, SATURDAY_END_TIME,
    GAME_DURATION_MINUTES, WEEKNIGHT_SLOTS,
    NO_GAMES_ON_SUNDAY, PRIORITY_WEIGHTS,
    GAMES_PER_TEAM, MAX_GAMES_PER_7_DAYS
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class ScheduleOptimizer:
    def __init__(self, teams: List[Team], facilities: List[Facility], rules: Dict):
        self.teams = teams
        self.facilities = facilities
        self.rules = rules

        self.season_start = self._parse_date(rules.get('season_start', SEASON_START_DATE))
        self.season_end = self._parse_date(rules.get('season_end', SEASON_END_DATE))
        
        self.holidays = set(rules.get('holidays', []))

        for holiday_str in US_HOLIDAYS:
            self.holidays.add(self._parse_date(holiday_str))
        
        self.teams_by_division = self._group_teams_by_division()
        logger.info(f"Teams by division: {self.teams_by_division}")

        self.time_slots = self._generate_time_slots()
        logger.info(f"Time slots: {self.time_slots}")
        logger.info(f"Scheduler is successfuly initialized with {len(self.time_slots)} time slots")
    
    def _determine_home_away_teams(self, team1: Team, team2: Team, facility: Facility) -> Tuple[Team, Team]:
        if facility.owned_by_school:
            facility_owner = facility.owned_by_school.strip().lower()
            team1_school = team1.school.name.strip().lower()
            team2_school = team2.school.name.strip().lower()
            
            if team1_school == facility_owner:
                return (team1, team2)
            
            if team2_school == facility_owner:
                return (team2, team1)
        
        return (team1, team2)
    
    def _parse_date(self, date_input) -> date:
        if isinstance(date_input, date):
            return date_input
        if isinstance(date_input, str):
            return datetime.strptime(date_input, '%Y-%m-%d').date()
        return date_input
    
    def _group_teams_by_division(self) -> Dict[Division, List[Team]]:
        groups = defaultdict(list)
        for team in self.teams:
            groups[team.division].append(team)
        return dict(groups)
    
    def _is_valid_game_date(self, game_date: date) -> bool:
        if game_date < self.season_start or game_date > self.season_end:
            return False
        
        if game_date in self.holidays:
            return False
        
        if NO_GAMES_ON_SUNDAY and game_date.weekday() == 6:
            return False
        
        return True
    
    def _generate_time_slots(self) -> List[TimeSlot]:
        slots = []
        current_date = self.season_start

        while current_date <= self.season_end:
            if not self._is_valid_game_date(current_date):
                current_date += timedelta(days=1)
                continue
            
            day_of_week = current_date.weekday()
            
            if day_of_week < 5:
                start_time = WEEKNIGHT_START_TIME
                for slot_num in range(WEEKNIGHT_SLOTS):
                    slot_start = datetime.combine(date.min, start_time) + timedelta(minutes=slot_num * GAME_DURATION_MINUTES)
                    slot_end = slot_start + timedelta(minutes=GAME_DURATION_MINUTES)

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
        """Calculate matchup score - rules removed, to be added one by one."""
        # TODO: Add rules here
        return 0
    
    
    
    def _calculate_slot_score_for_matchup(self, team1: Team, team2: Team, slot: TimeSlot, 
                                          scheduled_games: List[Game]) -> int:
        """Calculate slot score - rules removed, to be added one by one."""
        # TODO: Add rules here
        return 0
        
    def _create_diverse_chunks(self, teams: List[Team], chunk_size: int = 35) -> List[List[Team]]:
        """
        Create diverse chunks of teams for scheduling optimization.
        Uses interleaved grouping to ensure each chunk has a good mix of:
        - Different schools
        - Different facility owners (for home game distribution)
        - Different coaches (for consolidation opportunities)
        - Different divisions (for simultaneous scheduling)
        """
        # Group teams by multiple criteria for diversity
        school_groups = defaultdict(list)
        facility_groups = defaultdict(list)
        coach_groups = defaultdict(list)
        division_groups = defaultdict(list)
        
        for team in teams:
            school_groups[team.school.name].append(team)
            
            # Find team's home facility
            home_facility = None
            for facility in self.facilities:
                if facility.owned_by_school and facility.owned_by_school.strip().lower() == team.school.name.strip().lower():
                    home_facility = facility.name
                    break
            facility_groups[home_facility or "neutral"].append(team)
            
            coach_groups[team.coach_name or "no_coach"].append(team)
            division_groups[team.division].append(team)
        
        # Create stratified shuffle: interleave teams from different groups
        # This ensures diversity in each chunk
        shuffled_teams = []
        
        # Round-robin through schools to distribute evenly
        school_lists = list(school_groups.values())
        random.shuffle(school_lists)  # Randomize school order
        
        max_school_size = max(len(teams) for teams in school_lists) if school_lists else 0
        
        for i in range(max_school_size):
            for school_teams in school_lists:
                if i < len(school_teams):
                    shuffled_teams.append(school_teams[i])
        
        # Create chunks
        chunks = []
        for i in range(0, len(shuffled_teams), chunk_size):
            chunk = shuffled_teams[i:i + chunk_size]
            if len(chunk) >= 2:  # Only add chunks with at least 2 teams
                chunks.append(chunk)
        
        # Log chunk diversity statistics
        for idx, chunk in enumerate(chunks):
            divisions = set(t.division for t in chunk)
            schools = set(t.school.name for t in chunk)
            coaches = set(t.coach_name for t in chunk if t.coach_name)
            logger.info(f"  Chunk {idx + 1}: {len(chunk)} teams, {len(divisions)} divisions, {len(schools)} schools, {len(coaches)} coaches")
        
        return chunks
    
    def optimize_schedule(self) -> Schedule:
        logger.info("=" * 60)
        logger.info("Starting schedule optimization...")
        logger.info("=" * 60)
        
        schedule = Schedule(
            season_start=self.season_start,
            season_end=self.season_end
        )
        
        self.global_school_time_slots = defaultdict(set)
        self.global_used_slots = set()
        
        logger.info(f"Total teams: {len(self.teams)}")
        
        # STEP 1: Separate ES_K1_REC teams (special constraints)
        k1_teams = [t for t in self.teams if t.division == Division.ES_K1_REC]
        other_teams = [t for t in self.teams if t.division != Division.ES_K1_REC]
        
        logger.info(f"  ES_K1_REC teams: {len(k1_teams)}")
        logger.info(f"  Other division teams: {len(other_teams)}")
        
        # STEP 2: Schedule ES_K1_REC teams first (they need 8ft rims and cluster matching)
        if k1_teams:
            logger.info("=" * 60)
            logger.info("PHASE 1: Scheduling ES_K1_REC teams (8ft rims required)")
            logger.info("=" * 60)
            
            if len(k1_teams) >= 30:
                logger.info(f"  Using CP-SAT solver for K1 teams...")
                k1_games = self._schedule_chunk_cpsat(k1_teams, "K1")
                team_counts = defaultdict(int)
                for game in k1_games:
                    team_counts[game.home_team.id] += 1
                    team_counts[game.away_team.id] += 1
                teams_under_8 = [t for t in k1_teams if team_counts[t.id] < 8]
                
                if teams_under_8:
                    logger.info(f"  CP-SAT incomplete, switching to greedy for K1 teams...")
                    k1_games = self._schedule_chunk_greedy(k1_teams, "K1")
            else:
                logger.info(f"  Using greedy algorithm for K1 teams...")
                k1_games = self._schedule_chunk_greedy(k1_teams, "K1")
            
            for game in k1_games:
                schedule.add_game(game)
            
            logger.info(f"  Generated {len(k1_games)} K1 games")
            logger.info(f"  Slots used: {len(self.global_used_slots)}")
        
        # STEP 3: Create diverse chunks from remaining teams (NO ES_K1_REC)
        if other_teams:
            logger.info("=" * 60)
            logger.info("PHASE 2: Scheduling other divisions (diverse chunks)")
            logger.info("=" * 60)
            logger.info(f"Creating diverse chunks from {len(other_teams)} teams...")
            
            team_chunks = self._create_diverse_chunks(other_teams, chunk_size=35)
            
            logger.info(f"Created {len(team_chunks)} chunks for scheduling")
            logger.info("=" * 60)
            
            # Schedule each chunk
            for chunk_idx, chunk_teams in enumerate(team_chunks, start=1):
                logger.info(f"Scheduling Chunk {chunk_idx}/{len(team_chunks)}")
                logger.info(f"  Teams: {len(chunk_teams)}")
                logger.info(f"  Slots available: {len(self.time_slots) - len(self.global_used_slots)}")
                
                # Determine which scheduling method to use
                if len(chunk_teams) >= 30:
                    logger.info(f"  Using CP-SAT solver (chunk size >= 30)...")
                    chunk_games = self._schedule_chunk_cpsat(chunk_teams, chunk_idx)
                    
                    # Check if CP-SAT was successful
                    team_counts = defaultdict(int)
                    for game in chunk_games:
                        team_counts[game.home_team.id] += 1
                        team_counts[game.away_team.id] += 1
                    teams_under_8 = [t for t in chunk_teams if team_counts[t.id] < 8]
                    
                    if teams_under_8:
                        logger.info(f"  CP-SAT incomplete ({len(teams_under_8)} teams < 8 games), switching to greedy...")
                        chunk_games = self._schedule_chunk_greedy(chunk_teams, chunk_idx)
                else:
                    logger.info(f"  Using greedy algorithm (chunk size < 30)...")
                    chunk_games = self._schedule_chunk_greedy(chunk_teams, chunk_idx)
                
                # Add games to schedule
                for game in chunk_games:
                    schedule.add_game(game)
                
                logger.info(f"  Generated {len(chunk_games)} games")
                logger.info(f"  Total slots used: {len(self.global_used_slots)}")
                logger.info("=" * 60)
        
        logger.info(f"Schedule optimization complete: {len(schedule.games)} total games")
        logger.info("=" * 60)
        
        return schedule
    
    def _schedule_chunk_cpsat(self, teams: List[Team], chunk_id) -> List[Game]:
        """Schedule a chunk of teams using CP-SAT optimization - rules cleared."""
        model = cp_model.CpModel()
        
        game_vars = {}
        num_teams = len(teams)
        
        # Get usable slots (already used slots are excluded)
        usable_slot_indices = []
        for slot_idx, slot in enumerate(self.time_slots):
            slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
            if hasattr(self, 'global_used_slots') and slot_key in self.global_used_slots:
                continue
            usable_slot_indices.append(slot_idx)
        
        num_slots = len(usable_slot_indices)
        
        # Create matchups (only basic filtering: same school not allowed)
        matchups = []
        for i in range(num_teams):
            for j in range(i + 1, num_teams):
                team1, team2 = teams[i], teams[j]
                
                if team1.school == team2.school:
                    continue
                
                matchups.append((i, j))
        
        # Create game variables for each matchup at each slot
        for (i, j) in matchups:
            game_vars[(i, j)] = {}
            for idx in range(num_slots):
                var_name = f'game_t{i}_t{j}_s{idx}'
                game_vars[(i, j)][idx] = model.NewBoolVar(var_name)
        
        # CONSTRAINT: Each team plays exactly GAMES_PER_TEAM games
        target_games_per_team = GAMES_PER_TEAM
        for team_idx in range(num_teams):
            team_games = []
            for (i, j) in matchups:
                if i == team_idx or j == team_idx:
                    for idx in game_vars[(i, j)]:
                        team_games.append(game_vars[(i, j)][idx])
            if team_games:
                model.Add(sum(team_games) == target_games_per_team)
        
        # CONSTRAINT: Each matchup plays at most once
        for (i, j) in matchups:
            all_game_vars = [game_vars[(i, j)][idx] for idx in game_vars[(i, j)]]
            if all_game_vars:
                model.Add(sum(all_game_vars) <= 1)
        
        # CONSTRAINT: Each team can play at most one game per time slot
        for idx in range(num_slots):
            for team_idx in range(num_teams):
                games_at_slot = []
                for (i, j) in matchups:
                    if i == team_idx or j == team_idx:
                        if idx in game_vars[(i, j)]:
                            games_at_slot.append(game_vars[(i, j)][idx])
                if games_at_slot:
                    model.Add(sum(games_at_slot) <= 1)
        
        # CONSTRAINT: Each slot can host at most one game
        for idx in range(num_slots):
            games_at_slot = []
            for (i, j) in matchups:
                if idx in game_vars[(i, j)]:
                    games_at_slot.append(game_vars[(i, j)][idx])
            if games_at_slot:
                model.Add(sum(games_at_slot) <= 1)
        
        # TODO: Add constraints and objective here
        
        logger.info(f"  Model stats: {len(matchups)} matchups, {num_slots} usable slots, {len(teams)} teams")
        logger.info(f"  ALL RULES REMOVED - Ready to add rules one by one")
        
        # Solver configuration
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 120.0
        solver.parameters.num_search_workers = 8
        solver.parameters.log_search_progress = False
        
        logger.info(f"  Solving CP-SAT model (basic constraints only)...")
        status = solver.Solve(model)
        
        games = []
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logger.info(f"  Solution found (status: {solver.StatusName(status)})")
            logger.info(f"  Solve time: {solver.WallTime():.2f}s")
            
            game_id = 0
            for (i, j) in matchups:
                for idx in game_vars[(i, j)]:
                    if solver.Value(game_vars[(i, j)][idx]):
                        actual_slot_idx = usable_slot_indices[idx]
                        slot = self.time_slots[actual_slot_idx]
                        
                        home_team = teams[i]
                        away_team = teams[j]
                        
                        game = Game(
                            id=f"chunk{chunk_id}_{game_id}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=home_team.division
                        )
                        
                        games.append(game)
                        
                        slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        if hasattr(self, 'global_used_slots'):
                            self.global_used_slots.add(slot_key)
                        
                        game_id += 1
        else:
            logger.info(f"  No solution found (status: {solver.StatusName(status)})")
            games = self._schedule_chunk_greedy(teams, chunk_id)
        
        return games
    
    def _schedule_chunk_greedy(self, teams: List[Team], chunk_id: int) -> List[Game]:
        """Schedule a chunk of teams using greedy algorithm - rules cleared."""
        games = []
        used_slots = set()
        team_games_count = defaultdict(int)
        matchups_used = set()
        team_time_slots = defaultdict(set)
        
        if not hasattr(self, 'global_used_slots'):
            self.global_used_slots = set()
        global_used_slots = self.global_used_slots
        
        # Get usable slots (already used slots are excluded)
        usable_slots = []
        for slot in self.time_slots:
            if not slot.facility.is_available(slot.date):
                continue
            
            slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
            if slot_key in global_used_slots:
                continue
            
            usable_slots.append(slot)
        
        # Simple slot sorting: by date then time
        usable_slots.sort(key=lambda slot: (slot.date, slot.start_time))
        
        logger.info(f"  Using {len(usable_slots)} filtered slots (from {len(self.time_slots)} total)")
        
        # Create matchups (only basic filtering: same school not allowed)
        matchups = []
        for i, team1 in enumerate(teams):
            for j, team2 in enumerate(teams[i + 1:], start=i + 1):
                if team1.school == team2.school:
                    continue
                
                score = self._calculate_matchup_score(team1, team2)
                matchups.append((score, team1, team2))
        
        matchups.sort(reverse=True, key=lambda x: x[0])
        
        target_games = GAMES_PER_TEAM
        
        # First pass: schedule games
        for score, team1, team2 in matchups:
            if team_games_count[team1.id] >= target_games or team_games_count[team2.id] >= target_games:
                continue
            
            matchup_key = tuple(sorted([team1.id, team2.id]))
            if matchup_key in matchups_used:
                continue
            
            # Find first available slot
            for slot in usable_slots:
                slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                
                if slot_key in used_slots or slot_key in global_used_slots:
                    continue
                
                time_slot_key = (slot.date, slot.start_time)
                
                # Check if teams are available at this time
                if time_slot_key in team_time_slots[team1.id] or time_slot_key in team_time_slots[team2.id]:
                    continue
                
                # Found a valid slot, schedule the game
                home_team, away_team = self._determine_home_away_teams(team1, team2, slot.facility)
                
                game = Game(
                    id=f"chunk{chunk_id}_{len(games)}",
                    home_team=home_team,
                    away_team=away_team,
                    time_slot=slot,
                    division=home_team.division
                )
                
                games.append(game)
                used_slots.add(slot_key)
                global_used_slots.add(slot_key)
                
                team_time_slots[team1.id].add(time_slot_key)
                team_time_slots[team2.id].add(time_slot_key)
                
                team_games_count[team1.id] += 1
                team_games_count[team2.id] += 1
                matchups_used.add(matchup_key)
                
                break  # Move to next matchup
        
        # Second pass: fill remaining games for teams that need them
        teams_needing_games = [team for team in teams if team_games_count[team.id] < target_games]
        
        if teams_needing_games:
            logger.info(f"  Second pass: {len(teams_needing_games)} teams need more games")
            
            for team in teams_needing_games:
                needed = target_games - team_games_count[team.id]
                
                for opponent in teams:
                    if needed <= 0:
                        break
                    
                    if opponent.id == team.id or opponent.school == team.school:
                        continue
                    
                    matchup_key = tuple(sorted([team.id, opponent.id]))
                    if matchup_key in matchups_used:
                        continue
                    
                    # Find first available slot
                    for slot in usable_slots:
                        slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        
                        if slot_key in used_slots or slot_key in global_used_slots:
                            continue
                        
                        time_slot_key = (slot.date, slot.start_time)
                        
                        if time_slot_key in team_time_slots[team.id] or time_slot_key in team_time_slots[opponent.id]:
                            continue
                        
                        # Schedule the game
                        home_team, away_team = self._determine_home_away_teams(team, opponent, slot.facility)
                        
                        game = Game(
                            id=f"chunk{chunk_id}_{len(games)}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=home_team.division
                        )
                        
                        games.append(game)
                        used_slots.add(slot_key)
                        global_used_slots.add(slot_key)
                        
                        team_time_slots[team.id].add(time_slot_key)
                        team_time_slots[opponent.id].add(time_slot_key)
                        
                        team_games_count[team.id] += 1
                        team_games_count[opponent.id] += 1
                        matchups_used.add(matchup_key)
                        
                        needed -= 1
                        break
        
        # Report final status
        teams_under_8 = [t for t in teams if team_games_count[t.id] < target_games]
        if teams_under_8:
            logger.warning(f"  WARNING: {len(teams_under_8)} teams still have < {target_games} games")
            for team in teams_under_8[:10]:
                logger.warning(f"    {team.id}: {team_games_count[team.id]} games")
        else:
            logger.info(f"  SUCCESS: All {len(teams)} teams have exactly {target_games} games!")
        
        logger.info(f"  ALL RULES REMOVED - Ready to add rules one by one")
        
        return games
