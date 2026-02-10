from ortools.sat.python import cp_model
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict

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

        print(f"teams: {teams}")
        
        self.season_start = self._parse_date(rules.get('season_start', SEASON_START_DATE))
        self.season_end = self._parse_date(rules.get('season_end', SEASON_END_DATE))
        
        self.holidays = set(rules.get('holidays', []))

        for holiday_str in US_HOLIDAYS:
            self.holidays.add(self._parse_date(holiday_str))
        
        self.teams_by_division = self._group_teams_by_division()

        self.time_slots = self._generate_time_slots()
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

        logger.info(f"Generating time slots from {current_date} to {self.season_end}")
        
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

                    logger.info(f"Adding time slot: {slot_start} to {slot_end}")
                    
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
        
        for division, division_teams in self.teams_by_division.items():
            logger.info(f"Scheduling division: {division.value}")
            logger.info(f"  Teams: {len(division_teams)}")
            
            if len(division_teams) < 2:
                logger.info(f"  Skipping - not enough teams")
                continue
            
            if len(division_teams) >= 30:
                logger.info(f"  Using CP-SAT solver (large division, 30s timeout)...")
                division_games = self._schedule_division(division, division_teams)
                team_counts = defaultdict(int)
                for game in division_games:
                    team_counts[game.home_team.id] += 1
                    team_counts[game.away_team.id] += 1
                teams_under_8 = [t for t in division_teams if team_counts[t.id] < 8]
                if teams_under_8:
                    logger.info(f"  CP-SAT incomplete ({len(teams_under_8)} teams < 8 games), switching to greedy algorithm...")
                    division_games = self._greedy_schedule_division(division, division_teams)
            else:
                logger.info(f"  Using optimized greedy algorithm...")
                division_games = self._greedy_schedule_division(division, division_teams)
            
            for game in division_games:
                schedule.add_game(game)
            
            logger.info(f"  Generated {len(division_games)} games")
        
        logger.info("=" * 60)
        logger.info(f"Schedule optimization complete: {len(schedule.games)} total games")
        logger.info("=" * 60)
        
        return schedule
    
    def _schedule_division(self, division: Division, teams: List[Team]) -> List[Game]:
        model = cp_model.CpModel()
        
        game_vars = {}
        matchup_scores = {}
        
        num_teams = len(teams)
        
        usable_slot_indices = []
        schools_in_division = set(team.school.name for team in teams)
        
        for slot_idx, slot in enumerate(self.time_slots):
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
                
                if division == Division.ES_K1_REC:
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
        
        if objective_terms:
            model.Maximize(sum(objective_terms))
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_search_workers = 4
        solver.parameters.log_search_progress = False
        
        logger.info(f"  Solving CP-SAT model with home/away constraints (30s timeout)...")
        status = solver.Solve(model)
        
        games = []
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logger.info(f"  Solution found (status: {solver.StatusName(status)})")
            
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
                            id=f"{division.value}_{game_id}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=division
                        )
                        
                        games.append(game)
                        
                        slot_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        
                        if hasattr(self, 'global_used_slots'):
                            self.global_used_slots.add(slot_key)
                        
                        game_id += 1
        else:
            logger.info(f"  No solution found (status: {solver.StatusName(status)})")
            games = self._greedy_schedule_division(division, teams)
        
        return games
    
    def _greedy_schedule_division(self, division: Division, teams: List[Team]) -> List[Game]:
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
            if division == Division.ES_K1_REC and not slot.facility.has_8ft_rims:
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
                    
                if division == Division.ES_K1_REC:
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
                id=f"{division.value}_{len(games)}",
                home_team=home_team,
                away_team=away_team,
                time_slot=slot,
                division=division
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
                        id=f"{division.value}_{len(games)}",
                        home_team=home_team,
                        away_team=away_team,
                        time_slot=slot,
                        division=division
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
                            id=f"{division.value}_{len(games)}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=division
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
