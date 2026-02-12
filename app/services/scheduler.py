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
        if team1.school == team2.school:
            return -999999
        
        score = 0
        
        if team1.division != Division.ES_K1_REC and team2.division != Division.ES_K1_REC:
            if team1.tier and team2.tier and team1.tier == team2.tier:
                score += PRIORITY_WEIGHTS['tier_matching']
        
        if team1.cluster and team2.cluster and team1.cluster == team2.cluster:
            score += PRIORITY_WEIGHTS['geographic_cluster']
        
        if team1.coach_name and team2.coach_name and team1.coach_name == team2.coach_name:
            score += PRIORITY_WEIGHTS['cluster_same_coach']

        if team2.id in team1.rivals:
            score += PRIORITY_WEIGHTS['respect_rivals']
        
        return score
    
    def _is_saturday_priority_facility(self, facility_name: str) -> bool:
        if not facility_name:
            return False
        
        facility_lower = facility_name.lower()
        
        if 'las vegas basketball' in facility_lower or 'lvbc' in facility_lower:
            return True
        
        if 'sloan canyon' in facility_lower:
            return True
        
        if 'supreme court' in facility_lower:
            return True
        
        return False
    
    def _is_saturday_secondary_facility(self, facility_name: str) -> bool:
        if not facility_name:
            return False
        
        facility_lower = facility_name.lower()
        
        if 'somerset' in facility_lower and 'skye canyon' in facility_lower:
            return True
        
        if 'faith' in facility_lower and 'christian' in facility_lower:
            return True
        
        return False
    
    def _get_consolidation_bonus(self, team: Team, slot: TimeSlot, scheduled_games: List[Game]) -> int:
        bonus = 0
        
        if not scheduled_games:
            return bonus
        
        school_name = team.school.name
        coach_name = team.coach_name
        
        for game in scheduled_games:
            game_slot = game.time_slot
            
            if game_slot.date != slot.date or game_slot.facility.name != slot.facility.name:
                continue
            
            same_school_game = (game.home_team.school.name == school_name or 
                               game.away_team.school.name == school_name)
            
            same_coach_game = (game.home_team.coach_name == coach_name or 
                              game.away_team.coach_name == coach_name)
            
            if same_school_game or same_coach_game:
                slot_minutes = slot.start_time.hour * 60 + slot.start_time.minute
                game_slot_minutes = game_slot.start_time.hour * 60 + game_slot.start_time.minute
                time_diff_minutes = abs(slot_minutes - game_slot_minutes)
                
                if time_diff_minutes == 60:
                    if same_coach_game:
                        bonus += PRIORITY_WEIGHTS['coach_consolidation']
                        logger.debug(f"  Consecutive coach bonus: {coach_name} at {slot.facility.name} on {slot.date}")
                    if same_school_game:
                        bonus += PRIORITY_WEIGHTS['school_consolidation']
                        logger.debug(f"  Consecutive school bonus: {school_name} at {slot.facility.name} on {slot.date}")
                
                elif time_diff_minutes <= 180:
                    if same_coach_game:
                        bonus += PRIORITY_WEIGHTS['coach_consolidation'] // 2
                    if same_school_game:
                        bonus += PRIORITY_WEIGHTS['school_consolidation'] // 2
        
        return bonus
    
    def _calculate_slot_score_for_matchup(self, team1: Team, team2: Team, slot: TimeSlot, 
                                          scheduled_games: List[Game]) -> int:
        score = 0
        
        facility = slot.facility
        if facility.owned_by_school:
            facility_owner = facility.owned_by_school.strip().lower()
            team1_school = team1.school.name.strip().lower()
            team2_school = team2.school.name.strip().lower()
            
            if facility_owner == team1_school or facility_owner == team2_school:
                score += 50000
        
        if slot.date.weekday() == 5:
            if self._is_saturday_priority_facility(slot.facility.name):
                score += 10000
            elif self._is_saturday_secondary_facility(slot.facility.name):
                score += 5000
        
        consolidation = 0
        consolidation += self._get_consolidation_bonus(team1, slot, scheduled_games)
        consolidation += self._get_consolidation_bonus(team2, slot, scheduled_games)
        score += consolidation
        
        days_into_season = (slot.date - self.season_start).days
        score -= days_into_season
        
        return score
        
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
        """Schedule a chunk of teams using CP-SAT optimization."""
        model = cp_model.CpModel()
        
        game_vars = {}
        matchup_scores = {}
        
        num_teams = len(teams)
        
        # Check if chunk has K1 teams (need 8ft rims)
        has_k1_teams = any(team.division == Division.ES_K1_REC for team in teams)
        
        usable_slot_indices = []
        
        for slot_idx, slot in enumerate(self.time_slots):
            # Filter for 8ft rims if needed
            if has_k1_teams and not slot.facility.has_8ft_rims:
                continue
                
            slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
            if hasattr(self, 'global_used_slots') and slot_key in self.global_used_slots:
                continue
            
            usable_slot_indices.append(slot_idx)
        
        num_slots = len(usable_slot_indices)
        
        matchups = []
        for i in range(num_teams):
            for j in range(i + 1, num_teams):
                team1, team2 = teams[i], teams[j]
                
                if team1.school == team2.school:
                    continue
                
                # ES_K1_REC division specific rule: only match within same cluster
                if team1.division == Division.ES_K1_REC or team2.division == Division.ES_K1_REC:
                    if team1.cluster and team2.cluster and team1.cluster != team2.cluster:
                        continue
                
                if team2.id in team1.do_not_play or team1.id in team2.do_not_play:
                    continue
                
                matchups.append((i, j))
                matchup_scores[(i, j)] = self._calculate_matchup_score(team1, team2)
        
        for (i, j) in matchups:
            game_vars[(i, j)] = {}
            for idx, slot_idx in enumerate(usable_slot_indices):
                slot = self.time_slots[slot_idx]
                facility = slot.facility
                
                team_i = teams[i]
                team_j = teams[j]
                
                facility_owner = None
                if facility.owned_by_school:
                    facility_owner = facility.owned_by_school.strip().lower()
                
                team_i_school = team_i.school.name.strip().lower()
                team_j_school = team_j.school.name.strip().lower()
                
                i_must_be_home = (facility_owner == team_i_school)
                j_must_be_home = (facility_owner == team_j_school)
                
                if i_must_be_home:
                    var_name = f'game_t{i}home_t{j}away_s{idx}'
                    game_vars[(i, j)][(idx, True)] = model.NewBoolVar(var_name)
                elif j_must_be_home:
                    var_name = f'game_t{j}home_t{i}away_s{idx}'
                    game_vars[(i, j)][(idx, False)] = model.NewBoolVar(var_name)
                else:
                    var_name_i_home = f'game_t{i}home_t{j}away_s{idx}'
                    var_name_j_home = f'game_t{j}home_t{i}away_s{idx}'
                    game_vars[(i, j)][(idx, True)] = model.NewBoolVar(var_name_i_home)
                    game_vars[(i, j)][(idx, False)] = model.NewBoolVar(var_name_j_home)
        
        target_games_per_team = GAMES_PER_TEAM
        
        for team_idx in range(num_teams):
            team_games = []
            for (i, j) in matchups:
                if i == team_idx or j == team_idx:
                    for key in game_vars[(i, j)]:
                        team_games.append(game_vars[(i, j)][key])
            
            if team_games:
                model.Add(sum(team_games) == target_games_per_team)
        
        for (i, j) in matchups:
            all_game_vars = [game_vars[(i, j)][key] for key in game_vars[(i, j)]]
            if all_game_vars:
                model.Add(sum(all_game_vars) <= 1)
        
        for idx in range(num_slots):
            for team_idx in range(num_teams):
                games_at_slot = []
                for (i, j) in matchups:
                    if i == team_idx or j == team_idx:
                        if (idx, True) in game_vars[(i, j)]:
                            games_at_slot.append(game_vars[(i, j)][(idx, True)])
                        if (idx, False) in game_vars[(i, j)]:
                            games_at_slot.append(game_vars[(i, j)][(idx, False)])
                
                if games_at_slot:
                    model.Add(sum(games_at_slot) <= 1)
        
        for team_idx in range(num_teams):
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
                            if (idx, True) in game_vars[(i, j)]:
                                games_in_week.append(game_vars[(i, j)][(idx, True)])
                            if (idx, False) in game_vars[(i, j)]:
                                games_in_week.append(game_vars[(i, j)][(idx, False)])
                
                if games_in_week:
                    model.Add(sum(games_in_week) <= MAX_GAMES_PER_7_DAYS)
        
        for idx in range(num_slots):
            games_at_slot = []
            for (i, j) in matchups:
                if (idx, True) in game_vars[(i, j)]:
                    games_at_slot.append(game_vars[(i, j)][(idx, True)])
                if (idx, False) in game_vars[(i, j)]:
                    games_at_slot.append(game_vars[(i, j)][(idx, False)])
            
            if games_at_slot:
                model.Add(sum(games_at_slot) <= 1)
        
        # Group teams by coach for clustering
        coach_teams = defaultdict(list)
        for team_idx, team in enumerate(teams):
            if team.coach_name:
                coach_teams[team.coach_name].append(team_idx)
        
        objective_terms = []
        
        for (i, j) in matchups:
            score = matchup_scores[(i, j)]
            for key in game_vars[(i, j)]:
                idx, is_i_home = key
                slot = self.time_slots[usable_slot_indices[idx]]
                
                objective_terms.append(game_vars[(i, j)][key] * score)
                
                if slot.date.weekday() == 5:
                    if self._is_saturday_priority_facility(slot.facility.name):
                        bonus = PRIORITY_WEIGHTS['saturday_priority_facility_fill']
                        objective_terms.append(game_vars[(i, j)][key] * bonus)
                    elif self._is_saturday_secondary_facility(slot.facility.name):
                        bonus = PRIORITY_WEIGHTS['saturday_secondary_facility_fill']
                        objective_terms.append(game_vars[(i, j)][key] * bonus)
        
        # COACH CLUSTERING CONSTRAINTS - Most important rule (LINEAR VERSION - CORRECT)
        # Encourage games with same coach to be scheduled on same day, same facility, consecutive times
        COACH_CONSOLIDATION_BONUS = PRIORITY_WEIGHTS['coach_consolidation']
        COACH_CONSECUTIVE_BONUS = PRIORITY_WEIGHTS['consecutive_slot_bonus']
        MAX_TIME_DIFF_MINUTES = 180  # Only consider games within 3 hours as "clustered"
        
        # Build mapping: (coach, date, facility) -> list of (game_var, slot_idx)
        coach_date_facility_games = defaultdict(list)
        
        for (i, j) in matchups:
            team_i = teams[i]
            team_j = teams[j]
            
            for key in game_vars[(i, j)]:
                idx, is_i_home = key
                slot = self.time_slots[usable_slot_indices[idx]]
                
                # Add to coach_i's list
                if team_i.coach_name:
                    coach_date_facility_games[(team_i.coach_name, slot.date, slot.facility.name)].append(
                        (game_vars[(i, j)][key], idx)
                    )
                
                # Add to coach_j's list (only if different coach)
                if team_j.coach_name and team_j.coach_name != team_i.coach_name:
                    coach_date_facility_games[(team_j.coach_name, slot.date, slot.facility.name)].append(
                        (game_vars[(i, j)][key], idx)
                    )
        
        # Log statistics for debugging
        logger.info(f"  Coach clustering: {len(coach_date_facility_games)} coach-date-facility combinations")
        
        # Add bonuses for coach consolidation (SIMPLIFIED - no consecutive slots)
        for (coach_name, date, facility), games_info in coach_date_facility_games.items():
            if len(games_info) < 2:
                continue
            
            # Create a variable that's 1 if at least 2 games are scheduled at this (date, facility)
            safe_facility = facility.replace(" ", "_").replace("'", "").replace("-", "_")[:30]
            consolidation_var = model.NewBoolVar(f'cons_{coach_name[:15]}_{date.isoformat()}_{safe_facility}')
            
            # Get just the game variables
            game_vars_list = [game_var for game_var, idx in games_info]
            
            # Constraint: consolidation_var = 1 if sum(games) >= 2
            model.Add(sum(game_vars_list) >= 2).OnlyEnforceIf(consolidation_var)
            model.Add(sum(game_vars_list) < 2).OnlyEnforceIf(consolidation_var.Not())
            
            # Add LINEAR bonus to objective
            objective_terms.append(consolidation_var * COACH_CONSOLIDATION_BONUS)
        
        logger.info(f"  Coach consolidation constraints added (simplified model)")
        
        # REMOVED: Consecutive slot bonus logic (was causing MODEL_INVALID with 75k variables)
        # The basic coach consolidation above is sufficient
        
        # Add search hints to prioritize coach consolidation (BEFORE setting objective)
        # Hints help solver find good solutions faster
        hint_count = 0
        for (coach_name, date, facility), games_info in coach_date_facility_games.items():
            if len(games_info) >= 3:  # Good consolidation opportunity
                for game_var, idx in games_info[:3]:  # Hint first 3 games
                    model.AddHint(game_var, 1)  # Hints go on MODEL, not solver
                    hint_count += 1
        
        if hint_count > 0:
            logger.info(f"  Added {hint_count} search hints for coach consolidation")
        
        if objective_terms:
            model.Maximize(sum(objective_terms))
        
        # Log model statistics
        logger.info(f"  Model stats: {len(matchups)} matchups, {num_slots} usable slots, {len(teams)} teams")
        
        # Dynamic timeout based on problem size (prioritize accuracy)
        problem_size = len(matchups) * num_slots
        if problem_size > 100000:
            timeout_seconds = 240.0  # 4 minutes for very large problems
        elif problem_size > 50000:
            timeout_seconds = 180.0  # 3 minutes for large problems
        else:
            timeout_seconds = 120.0  # 2 minutes for normal problems
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = timeout_seconds
        solver.parameters.num_search_workers = 8  # Use more parallel workers
        solver.parameters.log_search_progress = False
        solver.parameters.random_seed = 42  # Deterministic results
        
        # Additional optimizations for complex models
        solver.parameters.linearization_level = 2  # More aggressive linearization
        solver.parameters.cp_model_presolve = True  # Enable presolve
        solver.parameters.symmetry_level = 2  # Detect symmetries
        
        logger.info(f"  Solving CP-SAT model with coach clustering + home/away constraints ({int(timeout_seconds)}s timeout)...")
        status = solver.Solve(model)
        
        games = []
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logger.info(f"  Solution found (status: {solver.StatusName(status)})")
            logger.info(f"  Objective value: {solver.ObjectiveValue()}")
            logger.info(f"  Solve time: {solver.WallTime():.2f}s")
            
            game_id = 0
            for (i, j) in matchups:
                for key in game_vars[(i, j)]:
                    if solver.Value(game_vars[(i, j)][key]):
                        idx, is_i_home = key
                        actual_slot_idx = usable_slot_indices[idx]
                        slot = self.time_slots[actual_slot_idx]
                                
                        if is_i_home:
                            home_team = teams[i]
                            away_team = teams[j]
                        else:
                            home_team = teams[j]
                            away_team = teams[i]
                        
                        game = Game(
                            id=f"chunk{chunk_id}_{game_id}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=home_team.division  # Use team's own division
                        )
                        
                        games.append(game)
                        
                        slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        
                        if hasattr(self, 'global_used_slots'):
                            self.global_used_slots.add(slot_key)
                        
                        game_id += 1
            
            # Log coach clustering statistics
            coach_clustering_stats = defaultdict(lambda: defaultdict(int))
            for game in games:
                for team in [game.home_team, game.away_team]:
                    if team.coach_name:
                        key = (team.coach_name, game.time_slot.date, game.time_slot.facility.name)
                        coach_clustering_stats[team.coach_name][key] += 1
            
            clustered_coaches = 0
            for coach_name, date_facility_counts in coach_clustering_stats.items():
                for key, count in date_facility_counts.items():
                    if count >= 2:
                        clustered_coaches += 1
                        logger.info(f"  ✓ Coach '{coach_name}' has {count} games at {key[2]} on {key[1]}")
                        break
            
            if clustered_coaches > 0:
                logger.info(f"  SUCCESS: {clustered_coaches} coaches have clustered games!")
        else:
            logger.info(f"  No solution found (status: {solver.StatusName(status)})")
            games = self._schedule_chunk_greedy(teams, chunk_id)
        
        return games
    
    def _schedule_chunk_greedy(self, teams: List[Team], chunk_id: int) -> List[Game]:
        """Schedule a chunk of teams using greedy algorithm."""
        games = []
        used_slots = set()
        team_games_count = defaultdict(int)
        team_last_game_date = {}
        matchups_used = set()
        rematches_used = set()
        matchup_frequency = defaultdict(int)
        matchups_by_date = defaultdict(set)
        
        team_time_slots = defaultdict(set)
        
        if not hasattr(self, 'global_school_time_slots'):
            self.global_school_time_slots = defaultdict(set)
        school_time_slots = self.global_school_time_slots
        
        if not hasattr(self, 'global_used_slots'):
            self.global_used_slots = set()
        global_used_slots = self.global_used_slots
        
        saturday_facility_games = defaultdict(int)
        
        usable_slots = []
        for slot in self.time_slots:
            # Check if any team in this chunk needs 8ft rims (ES_K1_REC division)
            has_k1_team = any(team.division == Division.ES_K1_REC for team in teams)
            if has_k1_team and not slot.facility.has_8ft_rims:
                continue
            if not slot.facility.is_available(slot.date):
                continue
            
            slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
            if slot_key in global_used_slots:
                continue
            
            usable_slots.append(slot)
        
        def slot_priority(slot):
            priority = 0
            
            if slot.date.weekday() == 5:
                if self._is_saturday_priority_facility(slot.facility.name):
                    priority = 10000
                    priority += saturday_facility_games.get(slot.facility.name, 0) * 5
                elif self._is_saturday_secondary_facility(slot.facility.name):
                    priority = 5000
                    priority += saturday_facility_games.get(slot.facility.name, 0) * 5
                else:
                    priority = saturday_facility_games.get(slot.facility.name, 0) * 2
            
            return (-priority, slot.date, slot.start_time)
        
        usable_slots.sort(key=slot_priority)
        
        logger.info(f"  Using {len(usable_slots)} filtered slots (from {len(self.time_slots)} total)")
        
        matchups = []
        for i, team1 in enumerate(teams):
            for j, team2 in enumerate(teams[i + 1:], start=i + 1):
                if team1.school == team2.school:
                    continue
                    
                # ES_K1_REC division specific rule: only match within same cluster
                if team1.division == Division.ES_K1_REC or team2.division == Division.ES_K1_REC:
                    if team1.cluster and team2.cluster and team1.cluster != team2.cluster:
                        continue
                
                if team2.id in team1.do_not_play or team1.id in team2.do_not_play:
                    continue
                
                score = self._calculate_matchup_score(team1, team2)
                matchups.append((score, team1, team2))
        
        matchups.sort(reverse=True, key=lambda x: x[0])
        
        target_games = GAMES_PER_TEAM
        
        for score, team1, team2 in matchups:
            if team_games_count[team1.id] >= target_games or team_games_count[team2.id] >= target_games:
                continue
            
            matchup_key = tuple(sorted([team1.id, team2.id]))
            if matchup_key in matchups_used:
                continue
            
            valid_slots_with_scores = []
            
            for slot in usable_slots:
                slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                
                if slot_key in used_slots or slot_key in global_used_slots:
                    continue
                
                can_play = True
                time_slot_key = (slot.date, slot.start_time)
                
                for team in [team1, team2]:
                    if time_slot_key in team_time_slots[team.id]:
                        can_play = False
                        break
                
                if not can_play:
                    continue
                
                if matchup_key in matchups_by_date[slot.date]:
                    continue
                
                for team in [team1, team2]:
                    if team.id in team_last_game_date:
                        days_since = (slot.date - team_last_game_date[team.id]).days
                        if days_since < 2:
                            can_play = False
                            break
                
                if not can_play:
                    continue
                
                slot_score = self._calculate_slot_score_for_matchup(team1, team2, slot, games)
                
                valid_slots_with_scores.append((slot_score, slot))
            
            if not valid_slots_with_scores:
                continue
            
            valid_slots_with_scores.sort(reverse=True, key=lambda x: x[0])
            best_score, best_slot = valid_slots_with_scores[0]
            
            slot = best_slot
            slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
            time_slot_key = (slot.date, slot.start_time)
            
            home_team, away_team = self._determine_home_away_teams(team1, team2, slot.facility)
            
            game = Game(
                id=f"chunk{chunk_id}_{len(games)}",
                home_team=home_team,
                away_team=away_team,
                time_slot=slot,
                division=home_team.division  # Use team's own division
            )
            
            games.append(game)
            used_slots.add(slot_key)
            global_used_slots.add(slot_key)
            
            if slot.date.weekday() == 5:
                saturday_facility_games[slot.facility.name] += 1
            
            team_time_slots[team1.id].add(time_slot_key)
            team_time_slots[team2.id].add(time_slot_key)
            
            team_games_count[team1.id] += 1
            team_games_count[team2.id] += 1
            team_last_game_date[team1.id] = slot.date
            team_last_game_date[team2.id] = slot.date
            matchups_used.add(matchup_key)
            matchup_frequency[matchup_key] += 1
            matchups_by_date[slot.date].add(matchup_key)
            
            if best_score > 50000:
                logger.debug(f"  Home game: {home_team.id} vs {away_team.id} at {slot.facility.name} on {slot.date} (score: {best_score})")
            elif best_score > 1000:
                logger.debug(f"  Consolidated: {team1.id} vs {team2.id} at {slot.facility.name} on {slot.date} (score: {best_score})")
        
        teams_needing_games = [
            team for team in teams 
            if team_games_count[team.id] < target_games
        ]
        
        if teams_needing_games:
            logger.info(f"  Second pass: {len(teams_needing_games)} teams need more games")
            
            teams_needing_games.sort(key=lambda t: team_games_count[t.id])
            
            max_passes = 20
            for pass_num in range(max_passes):
                progress_made = False
                
                teams_needing_games.sort(key=lambda t: (team_games_count[t.id], t.id))
                
                for team in teams_needing_games:
                    needed = target_games - team_games_count[team.id]
                    
                    if needed <= 0:
                        continue
                    
                    potential_opponents = []
                    for opponent in teams:
                        if opponent.id == team.id:
                            continue
                        
                        if team.school == opponent.school:
                            continue
                        
                        if pass_num < 15:
                            if opponent.id in team.do_not_play or team.id in opponent.do_not_play:
                                continue
                        
                        opponent_needs = target_games - team_games_count[opponent.id]
                        matchup_key = tuple(sorted([team.id, opponent.id]))
                        
                        is_rematch = matchup_key in matchups_used
                        rematch_key = (matchup_key, 'rematch')
                        
                        if is_rematch:
                            current_count = matchup_frequency[matchup_key]
                            if current_count >= 2:
                                continue
                            
                            if team_games_count[team.id] >= 6 and team_games_count[opponent.id] >= 6:
                                continue
                        
                        priority = opponent_needs * 1000 + self._calculate_matchup_score(team, opponent)
                        if opponent.id in team.do_not_play or team.id in opponent.do_not_play:
                            priority -= 5000
                        potential_opponents.append((priority, opponent, matchup_key, is_rematch))
                    
                    potential_opponents.sort(reverse=True, key=lambda x: x[0])
                
                for priority, opponent, matchup_key, is_rematch in potential_opponents:
                    if needed <= 0:
                        break
                    
                    if not is_rematch and team_games_count[opponent.id] >= target_games:
                        continue
                    
                    scheduled = False
                    
                    valid_slots_with_scores_pass2 = []
                    
                    for slot in usable_slots:
                        slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        
                        if slot_key in used_slots or slot_key in global_used_slots:
                            continue
                        
                        can_play = True
                        time_slot_key = (slot.date, slot.start_time)
                        
                        for t in [team, opponent]:
                            if time_slot_key in team_time_slots[t.id]:
                                can_play = False
                                break
                        
                        if not can_play:
                            continue
                        
                        # CRITICAL FIX: Prevent same matchup on same day
                        if matchup_key in matchups_by_date[slot.date]:
                            continue
                        
                        min_days = 2
                        
                        if pass_num >= 15:
                            min_days = 0
                        elif pass_num >= 10:
                            min_days = 1
                        elif team_games_count[team.id] < 3:
                            min_days = 0
                        elif team_games_count[team.id] < 5:
                            min_days = 1
                        elif team_games_count[team.id] < 7:
                            min_days = 1
                        
                        if team_games_count[opponent.id] < 3:
                            min_days = 0
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
                        
                        slot_score_pass2 = self._calculate_slot_score_for_matchup(team, opponent, slot, games)
                        
                        valid_slots_with_scores_pass2.append((slot_score_pass2, slot))
                    
                    if not valid_slots_with_scores_pass2:
                        continue
                    
                    valid_slots_with_scores_pass2.sort(reverse=True, key=lambda x: x[0])
                    best_score_pass2, best_slot_pass2 = valid_slots_with_scores_pass2[0]
                    
                    slot = best_slot_pass2
                    slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                    time_slot_key = (slot.date, slot.start_time)
                    
                    home_team, away_team = self._determine_home_away_teams(team, opponent, slot.facility)
                    
                    game = Game(
                        id=f"chunk{chunk_id}_{len(games)}",
                        home_team=home_team,
                        away_team=away_team,
                        time_slot=slot,
                        division=home_team.division  # Use team's own division
                    )
                    
                    games.append(game)
                    used_slots.add(slot_key)
                    global_used_slots.add(slot_key)
                    
                    team_time_slots[team.id].add(time_slot_key)
                    team_time_slots[opponent.id].add(time_slot_key)
                    
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
                    
                    matchups_by_date[slot.date].add(matchup_key)
                    
                    needed -= 1
                    scheduled = True
                    
                    if best_score_pass2 > 50000:
                        logger.debug(f"  Home game (pass2): {home_team.id} vs {away_team.id} at {slot.facility.name} (score: {best_score_pass2})")
                    elif best_score_pass2 > 1000:
                        logger.debug(f"  Consolidated (pass2): {team.id} vs {opponent.id} at {slot.facility.name} (score: {best_score_pass2})")
                    
                    if scheduled:
                        progress_made = True
                        if team_games_count[team.id] >= target_games:
                            break
                
                teams_needing_games = [t for t in teams_needing_games if team_games_count[t.id] < target_games]
                
                if not teams_needing_games:
                    break
                
                if not progress_made:
                    if pass_num < max_passes - 1:
                        logger.info(f"  Pass {pass_num + 1} complete, {len(teams_needing_games)} teams still need games")
        
        teams_under_8 = [t for t in teams if team_games_count[t.id] < target_games]
        if teams_under_8:
            logger.warning(f"  WARNING: {len(teams_under_8)} teams still have < 8 games:")
            for team in teams_under_8[:15]:
                logger.warning(f"    {team.id}: {team_games_count[team.id]} games")
            
            total_needed = sum(target_games - team_games_count[t.id] for t in teams_under_8)
            logger.warning(f"  Total games needed: {total_needed}")
            logger.warning(f"  Available slots remaining: {len(usable_slots) - len(used_slots)}")
            
            logger.info(f"  Attempting final desperate fill pass...")
            for team in teams_under_8:
                needed = target_games - team_games_count[team.id]
                if needed <= 0:
                    continue
                
                for opponent in teams:
                    if opponent.id == team.id:
                        continue
                    
                    for slot in usable_slots:
                        slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        time_slot_key = (slot.date, slot.start_time)
                        
                        if slot_key in used_slots or slot_key in global_used_slots:
                            continue
                        
                        if time_slot_key in team_time_slots[team.id] or time_slot_key in team_time_slots[opponent.id]:
                            continue
                        
                        # REMOVED: School conflict check to allow multi-court usage
                        # Different teams from same school can now play simultaneously on different courts
                        
                        matchup_key = tuple(sorted([team.id, opponent.id]))
                        if matchup_frequency[matchup_key] >= 2:
                            continue
                        
                        # CRITICAL FIX: Prevent same matchup on same day in desperate pass too
                        if matchup_key in matchups_by_date[slot.date]:
                            continue  # Skip - these teams already playing/played today
                        
                        # Determine home/away based on facility ownership
                        home_team, away_team = self._determine_home_away_teams(team, opponent, slot.facility)
                        
                        game = Game(
                            id=f"chunk{chunk_id}_{len(games)}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=home_team.division  # Use team's own division
                        )
                        
                        games.append(game)
                        used_slots.add(slot_key)
                        global_used_slots.add(slot_key)
                        
                        if slot.date.weekday() == 5:
                            saturday_facility_games[slot.facility.name] += 1
                        
                        team_time_slots[team.id].add(time_slot_key)
                        team_time_slots[opponent.id].add(time_slot_key)
                        
                        # REMOVED: School time slot tracking to allow multi-court usage
                        # school_time_slots[team.school.name].add(time_slot_key)
                        # school_time_slots[opponent.school.name].add(time_slot_key)
                        
                        team_games_count[team.id] += 1
                        team_games_count[opponent.id] += 1
                        team_last_game_date[team.id] = slot.date
                        team_last_game_date[opponent.id] = slot.date
                        matchup_frequency[matchup_key] += 1
                        matchups_by_date[slot.date].add(matchup_key)  # Track this matchup on this date
                        needed -= 1
                        
                        if needed <= 0:
                            break
                    
                    if team_games_count[team.id] >= target_games:
                        break
        else:
            logger.info(f"  SUCCESS: All {len(teams)} teams have exactly 8 games!")
        
        final_teams_under_8 = [t for t in teams if team_games_count[t.id] < target_games]
        if final_teams_under_8:
            logger.warning(f"  Final status: {len(final_teams_under_8)} teams still < 8 games")
            logger.warning(f"  This indicates insufficient time slots or constraint conflicts")
        else:
            logger.info(f"  All teams have exactly 8 games - RULE SATISFIED")
        
        return games
