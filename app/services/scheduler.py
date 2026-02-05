from datetime import datetime, date, time, timedelta
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass
import itertools

from app.models import (
    Team, Facility, Game, TimeSlot, Division, Schedule, School
)
from app.core.config import (
    SEASON_START_DATE, SEASON_END_DATE, US_HOLIDAYS,
    WEEKNIGHT_START_TIME, WEEKNIGHT_END_TIME,
    SATURDAY_START_TIME, SATURDAY_END_TIME,
    GAME_DURATION_MINUTES,
    NO_GAMES_ON_SUNDAY,
    PRIORITY_WEIGHTS
)

@dataclass
class SchoolMatchup:
    school_a: School
    school_b: School
    games: List[Tuple[Team, Team, Division]]
    priority_score: float = 0.0
    
    def __hash__(self):
        return hash((self.school_a.name, self.school_b.name))

@dataclass
class TimeBlock:
    facility: Facility
    date: date
    start_time: time
    num_consecutive_slots: int
    court_number: int = 1
    duration_minutes: int = GAME_DURATION_MINUTES
    
    def get_slots(self, num_needed: int = None) -> List[TimeSlot]:
        if num_needed is None:
            num_needed = self.num_consecutive_slots
        
        slots = []
        current_time = self.start_time
        
        for i in range(min(num_needed, self.num_consecutive_slots)):
            end_datetime = datetime.combine(date.min, current_time) + timedelta(minutes=self.duration_minutes)
            slots.append(TimeSlot(
                date=self.date,
                start_time=current_time,
                end_time=end_datetime.time(),
                facility=self.facility,
                court_number=self.court_number
            ))
            current_time = end_datetime.time()
        
        return slots

class SchoolBasedScheduler:
    def __init__(self, teams: List[Team], facilities: List[Facility], rules: Dict):
        self.teams = teams
        self.facilities = facilities
        self.rules = rules
        
        self.season_start = self._parse_date(rules.get('season_start', SEASON_START_DATE))
        self.season_end = self._parse_date(rules.get('season_end', SEASON_END_DATE))
        
        self.holidays = set(rules.get('holidays', []))
        for holiday_str in US_HOLIDAYS:
            self.holidays.add(self._parse_date(holiday_str))
        
        self.school_blackouts = rules.get('blackouts', {})
        if self.school_blackouts:
            total_blackout_days = sum(len(dates) for dates in self.school_blackouts.values())
            print(f"Loaded {total_blackout_days} blackout dates for {len(self.school_blackouts)} schools")
        
        self.teams_by_school = self._group_teams_by_school()
        self.teams_by_division = self._group_teams_by_division()
        self.schools = list(self.teams_by_school.keys())
        
        self.time_blocks = self._generate_time_blocks()
        
        self.used_courts = set()
        self.team_game_count = defaultdict(int)
        self.team_game_dates = defaultdict(list)
        self.school_matchup_count = defaultdict(int)
        self.team_time_slots = defaultdict(set)
        self.school_game_dates = defaultdict(list)
        self.school_time_slots = defaultdict(set)
        self.coach_time_slots = defaultdict(set)
        self.school_opponents_on_court = {}
        
        self.school_facility_dates = {}
        
        self.school_weeknight_count = defaultdict(int)
        self.school_weeknights = defaultdict(set)
        
        self.facility_date_games = defaultdict(int)
        
        print(f"\nSchool-Based Scheduler initialized:")
        print(f"  Season: {self.season_start} to {self.season_end}")
        print(f"  Teams: {len(self.teams)}")
        print(f"  Schools: {len(self.schools)}")
        print(f"  Facilities: {len(self.facilities)}")
        print(f"  Time blocks: {len(self.time_blocks)}")
        
        self._check_cluster_coverage()
        self._report_data_quality()
    
    def _check_cluster_coverage(self):
        teams_with_cluster = [t for t in self.teams if t.cluster]
        teams_without_cluster = [t for t in self.teams if not t.cluster]
        
        coverage_pct = len(teams_with_cluster) / len(self.teams) * 100 if self.teams else 0
        
        print(f"\n{'='*80}")
        print("CLUSTER COVERAGE CHECK")
        print(f"{'='*80}")
        print(f"Teams with cluster: {len(teams_with_cluster)} ({coverage_pct:.1f}%)")
        print(f"Teams without cluster: {len(teams_without_cluster)}")
        
        if coverage_pct < 90:
            print(f"\n[WARNING] Only {coverage_pct:.1f}% of teams have cluster assignments!")
            print("[WARNING] Geographic clustering will be severely limited!")
            print("[CRITICAL] Cross-town travel will occur frequently!")
            print("\n[ACTION REQUIRED] Please assign clusters in Google Sheet:")
            print("  Tab: 'TIERS, CLUSTERS, RIVALS, DO NOT PLAY'")
            print("  Column: Cluster (e.g., Henderson, North Las Vegas, etc.)")
            
            schools_without = sorted(set(t.school.name for t in teams_without_cluster))
            print(f"\nSchools missing clusters ({len(schools_without)}):")
            for i, school in enumerate(schools_without[:25], 1):
                print(f"  {i}. {school}")
            if len(schools_without) > 25:
                print(f"  ... and {len(schools_without) - 25} more")
            
            print(f"\n{'='*80}")
            print("RECOMMENDATION: Assign clusters to ALL schools before scheduling")
            print(f"{'='*80}\n")
        else:
            print(f"\n[OK] Good cluster coverage ({coverage_pct:.1f}%)")
            print(f"{'='*80}\n")
    
    def _report_data_quality(self):
        print(f"\n{'='*80}")
        print("DATA QUALITY REPORT")
        print(f"{'='*80}")
        
        unique_schools = {}
        for team in self.teams:
            if team.school.name not in unique_schools:
                unique_schools[team.school.name] = team.school
        
        schools_with_tier = [name for name, school in unique_schools.items() if school.tier]
        schools_without_tier = [name for name, school in unique_schools.items() if not school.tier]
        
        tier_coverage = len(schools_with_tier) / len(unique_schools) * 100 if unique_schools else 0
        
        print(f"\n[TIER DATA]")
        print(f"  Schools with tier: {len(schools_with_tier)} ({tier_coverage:.1f}%)")
        print(f"  Schools without tier: {len(schools_without_tier)}")
        
        if schools_without_tier:
            print(f"\n  Schools missing tier data:")
            for school in sorted(schools_without_tier)[:10]:
                print(f"    - {school}")
            if len(schools_without_tier) > 10:
                print(f"    ... and {len(schools_without_tier) - 10} more")
        
        if hasattr(self, 'school_blackouts'):
            schools_with_blackouts = len(self.school_blackouts)
            print(f"\n[BLACKOUT DATA]")
            print(f"  Schools with blackouts: {schools_with_blackouts}")
            if schools_with_blackouts > 0:
                total_blackout_days = sum(len(dates) for dates in self.school_blackouts.values())
                print(f"  Total blackout dates: {total_blackout_days}")
        
        teams_per_school = defaultdict(int)
        for team in self.teams:
            teams_per_school[team.school.name] += 1
        
        small_schools = [(name, count) for name, count in teams_per_school.items() if count <= 2]
        large_schools = [(name, count) for name, count in teams_per_school.items() if count >= 6]
        
        print(f"\n[TEAM DISTRIBUTION]")
        print(f"  Schools with 1-2 teams: {len(small_schools)}")
        print(f"  Schools with 6+ teams: {len(large_schools)}")
        
        if small_schools:
            print(f"\n  Small schools (may have scheduling challenges):")
            for school, count in sorted(small_schools)[:5]:
                print(f"    - {school}: {count} team(s)")
        
        k1_facilities = [f for f in self.facilities if f.has_8ft_rims]
        print(f"\n[K-1 FACILITIES]")
        print(f"  Facilities with 8ft rims: {len(k1_facilities)}")
        for facility in k1_facilities:
            print(f"    - {facility.name}")
        
        print(f"\n{'='*80}")
        print("DATA QUALITY CHECK COMPLETE")
        print(f"{'='*80}\n")
        
        print(f"\n{'='*80}")
        print("FIRST WEEK FACILITY AVAILABILITY (Jan 5-11, 2026)")
        print(f"{'='*80}")
        first_week_dates = [self.season_start + timedelta(days=i) for i in range(7)]
        
        key_facilities = [f for f in self.facilities if 'faith' in f.name.lower() or 'lvbc' in f.name.lower() or 'las vegas basketball' in f.name.lower()]
        
        if key_facilities:
            for facility in key_facilities:
                print(f"\n{facility.name}:")
                print(f"  Max courts: {facility.max_courts}")
                print(f"  Has available_dates list: {len(facility.available_dates) > 0} ({len(facility.available_dates)} dates)")
                print(f"  Has unavailable_dates list: {len(facility.unavailable_dates) > 0} ({len(facility.unavailable_dates)} dates)")
                
                for check_date in first_week_dates:
                    day_name = check_date.strftime("%A, %b %d")
                    is_avail = facility.is_available(check_date)
                    status = "✅" if is_avail else "❌"
                    print(f"    {status} {day_name}")
                    
                    if not is_avail:
                        if facility.unavailable_dates and check_date in facility.unavailable_dates:
                            print(f"       → Explicitly unavailable")
                        elif facility.available_dates and check_date not in facility.available_dates:
                            print(f"       → Not in available_dates list")
        else:
            print("  No Faith or LVBC facilities found")
            print(f"  Total facilities loaded: {len(self.facilities)}")
            if len(self.facilities) > 0:
                print(f"  First 5 facilities: {[f.name for f in self.facilities[:5]]}")
        
        print(f"{'='*80}\n")
    
    def _parse_date(self, date_input) -> date:
        if isinstance(date_input, date):
            return date_input
        if isinstance(date_input, str):
            return datetime.strptime(date_input, '%Y-%m-%d').date()
        return date_input
    
    def _group_teams_by_school(self) -> Dict[School, Dict[Division, List[Team]]]:
        groups = defaultdict(lambda: defaultdict(list))
        for team in self.teams:
            groups[team.school][team.division].append(team)
        return dict(groups)
    
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
    
    def _generate_time_blocks(self) -> List[TimeBlock]:
        blocks = []
        current_date = self.season_start
        
        while current_date <= self.season_end:
            if not self._is_valid_game_date(current_date):
                current_date += timedelta(days=1)
                continue
            
            day_of_week = current_date.weekday()
            
            if day_of_week < 5:
                time_slots = []
                current_time = WEEKNIGHT_START_TIME
                while current_time < WEEKNIGHT_END_TIME:
                    end_time = (datetime.combine(date.min, current_time) + timedelta(minutes=GAME_DURATION_MINUTES)).time()
                    if end_time <= WEEKNIGHT_END_TIME:
                        time_slots.append(current_time)
                    current_time = end_time
            elif day_of_week == 5:
                time_slots = []
                current_time = SATURDAY_START_TIME
                while current_time < SATURDAY_END_TIME:
                    end_time = (datetime.combine(date.min, current_time) + timedelta(minutes=GAME_DURATION_MINUTES)).time()
                    if end_time <= SATURDAY_END_TIME:
                        time_slots.append(current_time)
                    current_time = end_time
            else:
                current_date += timedelta(days=1)
                continue
            
            for facility in self.facilities:
                if facility.max_courts <= 0:
                    continue
                
                if not facility.is_available(current_date):
                    if current_date <= self.season_start + timedelta(days=7):
                        if facility.unavailable_dates and current_date in facility.unavailable_dates:
                            pass
                        elif facility.available_dates and current_date not in facility.available_dates:
                            pass
                    continue
                
                for court_num in range(1, facility.max_courts + 1):
                    for start_idx, start_time in enumerate(time_slots):
                        num_consecutive = len(time_slots) - start_idx
                        
                        blocks.append(TimeBlock(
                            facility=facility,
                            date=current_date,
                            start_time=start_time,
                            num_consecutive_slots=num_consecutive,
                            court_number=court_num
                        ))
            
            current_date += timedelta(days=1)
        
        return blocks
    
    def _generate_school_matchups(self) -> List[SchoolMatchup]:
        matchups = []
        
        for i, school_a in enumerate(self.schools):
            for school_b in self.schools[i + 1:]:
                if school_a.name == school_b.name:
                    continue
                
                games_for_matchup = []
                
                for division in Division:
                    teams_a = self.teams_by_school[school_a].get(division, [])
                    teams_b = self.teams_by_school[school_b].get(division, [])
                    
                    for team_a in teams_a:
                        for team_b in teams_b:
                            if team_a.school.name == team_b.school.name:
                                continue
                            
                            if team_b.id in team_a.do_not_play or team_a.id in team_b.do_not_play:
                                continue
                            
                            games_for_matchup.append((team_a, team_b, division))
                
                if games_for_matchup:
                    score = self._calculate_school_matchup_score(school_a, school_b, games_for_matchup)
                    matchups.append(SchoolMatchup(
                        school_a=school_a,
                        school_b=school_b,
                        games=games_for_matchup,
                        priority_score=score
                    ))
        
        matchups.sort(key=lambda m: m.priority_score, reverse=True)
        
        print(f"\nGenerated {len(matchups)} school matchups")
        return matchups
    
    def _calculate_school_matchup_score(self, school_a: School, school_b: School, games: List[Tuple[Team, Team, Division]]) -> float:
        if school_a.name == school_b.name:
            return float('-inf')
        
        score = 0.0
        same_cluster_count = 0
        cross_cluster_count = 0
        
        for team_a, team_b, division in games:
            if team_a.tier and team_b.tier:
                if team_a.tier == team_b.tier:
                    score += PRIORITY_WEIGHTS['tier_matching']
                else:
                    tier_diff = abs(int(team_a.tier.value.split()[-1]) - int(team_b.tier.value.split()[-1]))
                    score -= PRIORITY_WEIGHTS['tier_matching'] * tier_diff * 0.5
            
            if team_a.cluster and team_b.cluster:
                if team_a.cluster == team_b.cluster:
                    score += PRIORITY_WEIGHTS['geographic_cluster']
                    same_cluster_count += 1
                else:
                    base_penalty = PRIORITY_WEIGHTS['geographic_cluster']
                    score -= base_penalty * 50
                    cross_cluster_count += 1
            
            if team_b.id in team_a.rivals:
                score += PRIORITY_WEIGHTS['respect_rivals']
        
        if self._school_has_facility(school_a) or self._school_has_facility(school_b):
            score += 1000
        
        if same_cluster_count > 0 and cross_cluster_count == 0:
            score += 200
        
        for school in [school_a, school_b]:
            for facility in self.facilities:
                if self._facility_belongs_to_school(facility.name, school.name):
                    total_games_at_facility = sum(
                        count for (fac_name, _date), count in self.facility_date_games.items()
                        if fac_name == facility.name
                    )
                    
                    if total_games_at_facility < 10:
                        underutil_bonus = (10 - total_games_at_facility) * 10
                        score += underutil_bonus
        
        return score / len(games) if games else 0
    
    def _school_has_facility(self, school: School) -> bool:     
        school_lower = school.name.lower()
        for facility in self.facilities:
            facility_lower = facility.name.lower()
            if school_lower in facility_lower:
                return True
        return False
    
    def _cluster_games_by_coach(self, games: List[Tuple[Team, Team, Division]]) -> List[Tuple[Team, Team, Division]]:
        coach_games = defaultdict(list)
        for game in games:
            team_a, team_b, division = game
            coaches = set()
            if team_a.coach_name:
                coaches.add(team_a.coach_name)
            if team_b.coach_name:
                coaches.add(team_b.coach_name)
            
            for coach in coaches:
                coach_games[coach].append(game)
        
        ordered_games = []
        used_games = set()
        
        for coach, coach_game_list in sorted(coach_games.items(), key=lambda x: -len(x[1])):
            if len(coach_game_list) > 1:
                for game in coach_game_list:
                    game_key = (game[0].id, game[1].id, game[2])
                    if game_key not in used_games:
                        ordered_games.append(game)
                        used_games.add(game_key)
        
        for game in games:
            game_key = (game[0].id, game[1].id, game[2])
            if game_key not in used_games:
                ordered_games.append(game)
                used_games.add(game_key)
        
        return ordered_games
    
    def _is_start_or_end_of_day(self, game_date: date, start_time: time) -> bool:
        day_of_week = game_date.weekday()
        
        if day_of_week < 5:
            time_slots = []
            current_time = WEEKNIGHT_START_TIME
            while current_time < WEEKNIGHT_END_TIME:
                end_time = (datetime.combine(date.min, current_time) + timedelta(minutes=GAME_DURATION_MINUTES)).time()
                if end_time <= WEEKNIGHT_END_TIME:
                    time_slots.append(current_time)
                current_time = end_time
        elif day_of_week == 5:
            time_slots = []
            current_time = SATURDAY_START_TIME
            while current_time < SATURDAY_END_TIME:
                end_time = (datetime.combine(date.min, current_time) + timedelta(minutes=GAME_DURATION_MINUTES)).time()
                if end_time <= SATURDAY_END_TIME:
                    time_slots.append(current_time)
                current_time = end_time
        else:
            return False
        
        if not time_slots:
            return False
        
        return start_time == time_slots[0] or start_time == time_slots[-1]
    
    def _facility_belongs_to_school(self, facility_name: str, school_name: str) -> bool:
        facility_lower = facility_name.lower()
        school_lower = school_name.lower()
        
        facility_lower = facility_lower.replace('pincrest', 'pinecrest')
        school_lower = school_lower.replace('pincrest', 'pinecrest')
        
        color_suffixes = [' blue', ' black', ' white', ' red', ' gold', ' silver', ' navy', 
                         ' green', ' purple', ' orange', ' yellow']
        school_base = school_lower
        for suffix in color_suffixes:
            if school_base.endswith(suffix):
                school_base = school_base[:-len(suffix)].strip()
                break
        
        import re
        school_base = re.sub(r'\s+\d+[a-z]?$', '', school_base).strip()
        
        if school_base in facility_lower:
            return True
        
        if school_lower in facility_lower:
            return True
        
        return False
    
    def _find_time_block_for_matchup(
        self, 
        matchup: SchoolMatchup,
        relax_saturday_rest: bool = False,
        relax_weeknight_3game: bool = False
    ) -> Optional[Tuple[TimeBlock, List[TimeSlot], School]]:
        num_games = len(matchup.games)
        
        ordered_games = self._cluster_games_by_coach(matchup.games)
        
        home_facility_blocks = []
        neutral_blocks = []
        
        for block in self.time_blocks:
            school_a_home = self._facility_belongs_to_school(block.facility.name, matchup.school_a.name)
            school_b_home = self._facility_belongs_to_school(block.facility.name, matchup.school_b.name)
            
            facility_belongs_to_other_school = False
            if not school_a_home and not school_b_home:
                for team in self.teams:
                    if self._facility_belongs_to_school(block.facility.name, team.school.name):
                        facility_belongs_to_other_school = True
                        break
            
            if school_a_home:
                num_school_a_teams = len([t for t in self.teams if t.school == matchup.school_a])
                num_games = len(matchup.games)
                
                if num_games >= num_school_a_teams:
                    weight = 1000 + (num_games * 10)
                elif num_games >= 3:
                    weight = 500 + (num_games * 10)
                else:
                    weight = 100 + (num_games * 10)
                
                home_facility_blocks.append((block, matchup.school_a, weight))
                
            elif school_b_home:
                num_school_b_teams = len([t for t in self.teams if t.school == matchup.school_b])
                num_games = len(matchup.games)
                
                if num_games >= num_school_b_teams:
                    weight = 1000 + (num_games * 10)
                elif num_games >= 3:
                    weight = 500 + (num_games * 10)
                else:
                    weight = 100 + (num_games * 10)
                
                home_facility_blocks.append((block, matchup.school_b, weight))
            elif not facility_belongs_to_other_school:
                neutral_blocks.append((block, None, 1))
        
        home_facility_blocks.sort(key=lambda x: (-x[2], x[0].date, x[0].start_time))
        neutral_blocks.sort(key=lambda x: (x[0].date, x[0].start_time))
        
        all_blocks = home_facility_blocks + neutral_blocks
        
        for block, home_school, weight in all_blocks:
            if block.num_consecutive_slots < num_games:
                continue
                
            is_weeknight = block.date.weekday() < 5
            if is_weeknight and not relax_weeknight_3game:
                existing_games_at_facility = sum(
                    1 for (d, _t, f, c) in self.used_courts
                    if d == block.date and f == block.facility.name and c == block.court_number
                )
                
                total_games_after = existing_games_at_facility + num_games
                
                if total_games_after < 3:
                    continue
            
            if is_weeknight:
                school_a_weeknights = self.school_weeknights[matchup.school_a.name]
                school_b_weeknights = self.school_weeknights[matchup.school_b.name]
                
                if len(school_a_weeknights) > 0:
                    if block.date not in school_a_weeknights:
                        continue
                
                if len(school_b_weeknights) > 0:
                    if block.date not in school_b_weeknights:
                        continue
            
            slots_available = True
            test_slots = block.get_slots(num_games)
            
            for slot in test_slots:
                court_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                if court_key in self.used_courts:
                    slots_available = False
                    break
            
            if not slots_available:
                continue
            
            has_k1_rec = any(div == Division.ES_K1_REC for _, _, div in ordered_games)
            has_non_k1_rec = any(div != Division.ES_K1_REC for _, _, div in ordered_games)
            
            if has_k1_rec and not block.facility.has_8ft_rims:
                continue
            
            if block.facility.has_8ft_rims and has_non_k1_rec:
                continue
            
            has_23_rec = any(div == Division.ES_23_REC for _, _, div in ordered_games)
            if has_23_rec:
                if not self._is_start_or_end_of_day(block.date, block.start_time):
                    continue
            
            can_schedule = True
            test_slots = block.get_slots(num_games)
            
            if block.date.weekday() < 5:
                school_a_key = (matchup.school_a.name, block.date)
                school_b_key = (matchup.school_b.name, block.date)
                
                if school_a_key in self.school_facility_dates:
                    if self.school_facility_dates[school_a_key] != block.facility.name:
                        can_schedule = False
                
                if school_b_key in self.school_facility_dates:
                    if self.school_facility_dates[school_b_key] != block.facility.name:
                        can_schedule = False
                
                if not can_schedule:
                    continue
            
            schools_in_block = set()
            
            teams_in_matchup_on_date = defaultdict(int)
            
            for i, (team_a, team_b, division) in enumerate(ordered_games):
                if i >= len(test_slots):
                    can_schedule = False
                    break
                
                slot = test_slots[i]
                time_slot_key = (slot.date, slot.start_time)
                
                if time_slot_key in self.team_time_slots[team_a.id]:
                    can_schedule = False
                    break
                if time_slot_key in self.team_time_slots[team_b.id]:
                    can_schedule = False
                    break

                if time_slot_key in self.school_time_slots[team_a.school.name]:
                    can_schedule = False
                    break
                if time_slot_key in self.school_time_slots[team_b.school.name]:
                    can_schedule = False
                    break
                
                # CRITICAL: Check if either COACH is already busy at this specific time
                # This prevents "Doral Pebble (Ferrell) on 2 courts at same time"
                if time_slot_key in self.coach_time_slots[team_a.coach_name]:
                    can_schedule = False
                    break
                if time_slot_key in self.coach_time_slots[team_b.coach_name]:
                    can_schedule = False
                    break
                
                schools_in_block.add(team_a.school.name)
                schools_in_block.add(team_b.school.name)
                
                teams_in_matchup_on_date[team_a.id] += 1
                teams_in_matchup_on_date[team_b.id] += 1
                
                is_weeknight = block.date.weekday() < 5
                is_home_facility = self._facility_belongs_to_school(block.facility.name, team_a.school.name) or \
                                   self._facility_belongs_to_school(block.facility.name, team_b.school.name)
                
                court_date_key = (block.date, block.facility.name, block.court_number)
                schools_on_this_court = set()
                for (date, facility, court, school), opponent in self.school_opponents_on_court.items():
                    if date == block.date and facility == block.facility.name and court == block.court_number:
                        schools_on_this_court.add(school)
                        schools_on_this_court.add(opponent)
                
                if schools_on_this_court and is_weeknight and not is_home_facility:
                    current_matchup_schools = {team_a.school.name, team_b.school.name}
                    if current_matchup_schools != schools_on_this_court:
                        can_schedule = False
                        break
                
                court_key_a = (block.date, block.facility.name, block.court_number, team_a.school.name)
                court_key_b = (block.date, block.facility.name, block.court_number, team_b.school.name)
                
                if court_key_a in self.school_opponents_on_court:
                    expected_opponent = self.school_opponents_on_court[court_key_a]
                    if expected_opponent != team_b.school.name:
                        can_schedule = False
                        break
                
                if court_key_b in self.school_opponents_on_court:
                    expected_opponent = self.school_opponents_on_court[court_key_b]
                    if expected_opponent != team_a.school.name:
                        can_schedule = False
                        break
                
                if block.date.weekday() < 5:
                    if block.date in self.team_game_dates[team_a.id]:
                        can_schedule = False
                        break
                    if block.date in self.team_game_dates[team_b.id]:
                        can_schedule = False
                        break
                    
                    if teams_in_matchup_on_date[team_a.id] > 1:
                        can_schedule = False
                        break
                    if teams_in_matchup_on_date[team_b.id] > 1:
                        can_schedule = False
                        break
                
                if block.date.weekday() == 5 and not relax_saturday_rest:
                    is_rec_division = (division == Division.ES_K1_REC or division == Division.ES_23_REC)
                    
                    if not is_rec_division:
                        from datetime import datetime
                        
                        team_a_saturday_times = []
                        team_b_saturday_times = []
                        
                        for existing_time_key in self.team_time_slots[team_a.id]:
                            existing_date, existing_time = existing_time_key
                            if existing_date == block.date:
                                team_a_saturday_times.append(existing_time)
                        
                        for existing_time_key in self.team_time_slots[team_b.id]:
                            existing_date, existing_time = existing_time_key
                            if existing_date == block.date:
                                team_b_saturday_times.append(existing_time)
                        
                        for j in range(i):
                            prev_team_a, prev_team_b, prev_div = ordered_games[j]
                            prev_slot = test_slots[j]
                            
                            prev_is_rec = (prev_div == Division.ES_K1_REC or prev_div == Division.ES_23_REC)
                            if prev_is_rec:
                                continue
                            
                            if prev_team_a.id == team_a.id or prev_team_b.id == team_a.id:
                                team_a_saturday_times.append(prev_slot.start_time)
                            if prev_team_a.id == team_b.id or prev_team_b.id == team_b.id:
                                team_b_saturday_times.append(prev_slot.start_time)
                        
                        for existing_time in team_a_saturday_times:
                            existing_datetime = datetime.combine(block.date, existing_time)
                            new_datetime = datetime.combine(block.date, slot.start_time)
                            time_diff_minutes = abs((new_datetime - existing_datetime).total_seconds() / 60)
                            
                            if time_diff_minutes < 120:
                                can_schedule = False
                                print(f"      [SATURDAY REST] Blocked: {team_a.school.name} would have {time_diff_minutes:.0f}min between starts (need 120+ for 60min rest)")
                                break
                        
                        if can_schedule:
                            for existing_time in team_b_saturday_times:
                                existing_datetime = datetime.combine(block.date, existing_time)
                                new_datetime = datetime.combine(block.date, slot.start_time)
                                time_diff_minutes = abs((new_datetime - existing_datetime).total_seconds() / 60)
                                
                                if time_diff_minutes < 120:
                                    can_schedule = False
                                    print(f"      [SATURDAY REST] Blocked: {team_b.school.name} would have {time_diff_minutes:.0f}min between starts (need 120+ for 60min rest)")
                                    break
                
                if not can_schedule:
                    break
                
                if not self._can_team_play_on_date(team_a, block.date):
                    can_schedule = False
                    break
                if not self._can_team_play_on_date(team_b, block.date):
                    can_schedule = False
                    break
            
            if not can_schedule:
                continue
            
            if len(schools_in_block) > 2:
                continue
            
            matchup_key = tuple(sorted([matchup.school_a.name, matchup.school_b.name]))
            if self.school_matchup_count[matchup_key] >= 2:
                continue
                
            slots = block.get_slots(num_games)
            
            return (block, slots, home_school)
        
        return None
    
    def _can_team_play_on_date(self, team: Team, game_date: date) -> bool:
        if self.team_game_count[team.id] >= 8:
            return False
        
        if hasattr(self, 'school_blackouts') and team.school.name in self.school_blackouts:
            if game_date in self.school_blackouts[team.school.name]:
                return False
        
        team_dates = self.team_game_dates[team.id]
        
        if game_date.weekday() < 5:
            if game_date in team_dates:
                return False
        
        school_dates = self.school_game_dates[team.school.name]
        
        for existing_date in school_dates:
            days_diff = abs((game_date - existing_date).days)
            
            if days_diff == 1:
                if (existing_date.weekday() == 4 and game_date.weekday() == 5) or \
                   (existing_date.weekday() == 5 and game_date.weekday() == 4):
                    return False
        
        for existing_date in team_dates:
            days_diff = abs((game_date - existing_date).days)
            
            if days_diff < 7:
                games_in_7_days = sum(1 for d in team_dates if abs((d - game_date).days) < 7)
                if games_in_7_days >= 2:
                    return False
            
            if days_diff < 14:
                games_in_14_days = sum(1 for d in team_dates if abs((d - game_date).days) < 14)
                if games_in_14_days >= 3:
                    return False
        
        return True
    
    def optimize_schedule(self) -> Schedule:    
        print("\n" + "=" * 60)
        print("SCHOOL-BASED SCHEDULING (Redesigned Algorithm)")
        print("=" * 60)
        
        schedule = Schedule(
            season_start=self.season_start,
            season_end=self.season_end
        )
        
        matchups = self._generate_school_matchups()
        
        matchups_with_scores = [(m, self._calculate_school_matchup_score(m.school_a, m.school_b, m.games)) for m in matchups]
        matchups_with_scores.sort(key=lambda x: x[1], reverse=True)
        matchups = [m for m, score in matchups_with_scores]
        
        print(f"\nScheduling {len(matchups)} matchups (sorted by priority)...")
        print(f"  Top priority: Schools with home facilities (score boost: +1000)")
        print(f"  High priority: Rivals, same cluster, same tier")
        
        scheduled_count = 0
        failed_count = 0
        
        for matchup in matchups:
            result = self._find_time_block_for_matchup(matchup)
            
            if result:
                block, assigned_slots, home_school = result
                
                is_weeknight = block.date.weekday() < 5
                is_home_facility = home_school is not None
                
                if len(assigned_slots) < len(matchup.games):
                    failed_count += 1
                    continue
                
                for i, (team_a, team_b, division) in enumerate(matchup.games):
                    if i < len(assigned_slots):
                        slot = assigned_slots[i]
                        
                        if home_school:
                            if team_a.school == home_school:
                                home_team = team_a
                                away_team = team_b
                            else:
                                home_team = team_b
                                away_team = team_a
                        else:
                            home_team = team_a
                            away_team = team_b
                        
                        if slot.facility.has_8ft_rims and division != Division.ES_K1_REC:
                            print(f"    [K-1 VIOLATION PREVENTED] {division.value} attempted on {slot.facility.name}")
                            continue
                        
                        game = Game(
                            id=f"{division.value}_{len(schedule.games)}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=division
                        )
                        
                        schedule.add_game(game)
                        
                        self.team_game_count[team_a.id] += 1
                        self.team_game_count[team_b.id] += 1
                        self.team_game_dates[team_a.id].append(block.date)
                        self.team_game_dates[team_b.id].append(block.date)
                        
                        if block.date not in self.school_game_dates[team_a.school.name]:
                            self.school_game_dates[team_a.school.name].append(block.date)
                        if block.date not in self.school_game_dates[team_b.school.name]:
                            self.school_game_dates[team_b.school.name].append(block.date)
                        
                        court_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        self.used_courts.add(court_key)
                        
                        time_slot_key = (slot.date, slot.start_time)
                        self.team_time_slots[team_a.id].add(time_slot_key)
                        self.team_time_slots[team_b.id].add(time_slot_key)
                        
                        self.school_time_slots[team_a.school.name].add(time_slot_key)
                        self.school_time_slots[team_b.school.name].add(time_slot_key)
                        
                        self.coach_time_slots[team_a.coach_name].add(time_slot_key)
                        self.coach_time_slots[team_b.coach_name].add(time_slot_key)
                        
                        school_court_key_a = (slot.date, slot.facility.name, slot.court_number, team_a.school.name)
                        school_court_key_b = (slot.date, slot.facility.name, slot.court_number, team_b.school.name)
                        self.school_opponents_on_court[school_court_key_a] = team_b.school.name
                        self.school_opponents_on_court[school_court_key_b] = team_a.school.name
                        
                        school_date_key_a = (team_a.school.name, slot.date)
                        school_date_key_b = (team_b.school.name, slot.date)
                        self.school_facility_dates[school_date_key_a] = slot.facility.name
                        self.school_facility_dates[school_date_key_b] = slot.facility.name
                        
                        if slot.date.weekday() < 5:
                            self.school_weeknights[team_a.school.name].add(slot.date)
                            self.school_weeknights[team_b.school.name].add(slot.date)
                        
                        facility_date_key = (slot.facility.name, slot.date)
                        self.facility_date_games[facility_date_key] += 1
                
                matchup_key = tuple(sorted([matchup.school_a.name, matchup.school_b.name]))
                self.school_matchup_count[matchup_key] += 1
                
                scheduled_count += 1
            else:
                failed_count += 1
        
        print(f"\nFirst pass complete:")
        print(f"  Scheduled matchups: {scheduled_count}")
        print(f"  Failed matchups: {failed_count}")
        print(f"  Total games: {len(schedule.games)}")

        teams_under_8 = [t for t in self.teams if self.team_game_count[t.id] < 8]
        if teams_under_8:
            print(f"\n  {len(teams_under_8)} teams have < 8 games, starting rematch pass...")
            
            self._schedule_rematches(schedule, matchups, teams_under_8)
            
            teams_under_8 = [t for t in self.teams if self.team_game_count[t.id] < 8]
            if teams_under_8:
                print(f"\n  WARNING: {len(teams_under_8)} teams still have < 8 games after rematches")
                for team in teams_under_8[:10]:
                    print(f"    - {team.school.name} ({team.coach_name}): {self.team_game_count[team.id]} games")
        
        print("\n" + "=" * 60)
        print(f"Scheduling complete: {len(schedule.games)} total games")
        print("=" * 60)
        
        return schedule
    
    def _schedule_rematches(self, schedule: Schedule, matchups: List[SchoolMatchup], teams_needing_games: List[Team]):
        print("\n  Starting rematch pass to fill remaining games...")
        print("  Progressive constraint relaxation to ensure 8 games per team")
        
        max_passes = 10
        for pass_num in range(max_passes):
            teams_still_needing = [t for t in self.teams if self.team_game_count[t.id] < 8]
            if not teams_still_needing:
                break
            
            allow_partial_matchups = pass_num >= 2
            allow_multiple_facilities = pass_num >= 4
            allow_mixed_courts = pass_num >= 6
            relax_saturday_rest = pass_num >= 3
            relax_weeknight_3game = pass_num >= 7
            
            relaxation_status = []
            if allow_partial_matchups:
                relaxation_status.append("partial matchups")
            if allow_multiple_facilities:
                relaxation_status.append("multiple facilities")
            if allow_mixed_courts:
                relaxation_status.append("mixed courts")
            
            status_str = f" ({', '.join(relaxation_status)})" if relaxation_status else " (strict)"
            print(f"    Pass {pass_num + 1}: {len(teams_still_needing)} teams need games{status_str}")
            games_added = 0
            
            for matchup in matchups:
                matchup_key = tuple(sorted([matchup.school_a.name, matchup.school_b.name]))
                
                teams_in_matchup_need_games = False
                for team_a, team_b, division in matchup.games:
                    if self.team_game_count[team_a.id] < 8 or self.team_game_count[team_b.id] < 8:
                        teams_in_matchup_need_games = True
                        break
                
                if not teams_in_matchup_need_games:
                    continue
                
                max_rematches = 2 + pass_num
                if self.school_matchup_count[matchup_key] >= max_rematches:
                    continue
                
                result = self._find_time_block_for_matchup(
                    matchup,
                    relax_saturday_rest=relax_saturday_rest,
                    relax_weeknight_3game=relax_weeknight_3game
                )
            
            if result:
                block, assigned_slots, home_school = result
                
                teams_need_games = any(
                    self.team_game_count[team_a.id] < 8 or self.team_game_count[team_b.id] < 8
                    for team_a, team_b, division in matchup.games
                )
                
                if not teams_need_games:
                    continue
                
                if not allow_partial_matchups:
                    if len(assigned_slots) < len(matchup.games):
                        continue
                else:
                    if len(assigned_slots) == 0:
                        continue
                
                for i, (team_a, team_b, division) in enumerate(matchup.games):
                    if self.team_game_count[team_a.id] >= 8 and self.team_game_count[team_b.id] >= 8:
                        continue
                    
                    if i < len(assigned_slots):
                        slot = assigned_slots[i]
                        
                        if home_school:
                            if team_a.school == home_school:
                                home_team = team_a
                                away_team = team_b
                            else:
                                home_team = team_b
                                away_team = team_a
                        else:
                            home_team = team_a
                            away_team = team_b
                        
                        if slot.facility.has_8ft_rims and division != Division.ES_K1_REC:
                            print(f"    [K-1 VIOLATION PREVENTED - REMATCH] {division.value} attempted on {slot.facility.name}")
                            continue
                        
                        game = Game(
                            id=f"{division.value}_{len(schedule.games)}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=division
                        )
                        
                        schedule.add_game(game)
                        
                        self.team_game_count[team_a.id] += 1
                        self.team_game_count[team_b.id] += 1
                        self.team_game_dates[team_a.id].append(block.date)
                        self.team_game_dates[team_b.id].append(block.date)
                        
                        if block.date not in self.school_game_dates[team_a.school.name]:
                            self.school_game_dates[team_a.school.name].append(block.date)
                        if block.date not in self.school_game_dates[team_b.school.name]:
                            self.school_game_dates[team_b.school.name].append(block.date)
                        
                        court_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        self.used_courts.add(court_key)
                        
                        time_slot_key = (slot.date, slot.start_time)
                        self.team_time_slots[team_a.id].add(time_slot_key)
                        self.team_time_slots[team_b.id].add(time_slot_key)
                        
                        self.school_time_slots[team_a.school.name].add(time_slot_key)
                        self.school_time_slots[team_b.school.name].add(time_slot_key)
                        
                        self.coach_time_slots[team_a.coach_name].add(time_slot_key)
                        self.coach_time_slots[team_b.coach_name].add(time_slot_key)
                        
                        school_court_key_a = (slot.date, slot.facility.name, slot.court_number, team_a.school.name)
                        school_court_key_b = (slot.date, slot.facility.name, slot.court_number, team_b.school.name)
                        self.school_opponents_on_court[school_court_key_a] = team_b.school.name
                        self.school_opponents_on_court[school_court_key_b] = team_a.school.name
                        
                        school_date_key_a = (team_a.school.name, slot.date)
                        school_date_key_b = (team_b.school.name, slot.date)
                        self.school_facility_dates[school_date_key_a] = slot.facility.name
                        self.school_facility_dates[school_date_key_b] = slot.facility.name
                        
                        if slot.date.weekday() < 5:
                            self.school_weeknights[team_a.school.name].add(slot.date)
                            self.school_weeknights[team_b.school.name].add(slot.date)
                        
                        facility_date_key = (slot.facility.name, slot.date)
                        self.facility_date_games[facility_date_key] += 1
                
                self.school_matchup_count[matchup_key] += 1
                games_added += 1
            
            if games_added == 0:
                print(f"    No more games could be scheduled, stopping")
                break
        
        print(f"  Rematch pass complete: {len(schedule.games)} total games")
        
        teams_still_needing = [t for t in self.teams if self.team_game_count[t.id] < 8]
        if teams_still_needing:
            print(f"\n  AGGRESSIVE SATURDAY FILLING: {len(teams_still_needing)} teams still need games")
            self._fill_saturday_slots_aggressively(schedule, matchups, teams_still_needing)
    
    def _fill_saturday_slots_aggressively(self, schedule: Schedule, matchups: List[SchoolMatchup], teams_needing_games: List[Team]):
        print("    Starting aggressive Saturday slot filling...")
        print("    Relaxing: Saturday rest time, complete matchups, court reservation")
        
        max_fill_passes = 5
        for fill_pass in range(max_fill_passes):
            teams_still_needing = [t for t in self.teams if self.team_game_count[t.id] < 8]
            if not teams_still_needing:
                print(f"    ✅ All teams have 8 games!")
                break
            
            print(f"      Fill pass {fill_pass + 1}: {len(teams_still_needing)} teams need games")
            games_added = 0
            
            max_rematches = 5 + fill_pass
            
            saturday_blocks = [b for b in self.time_blocks if b.date.weekday() == 5]
            
            for block in saturday_blocks:
                for matchup in matchups:
                    matchup_key = tuple(sorted([matchup.school_a.name, matchup.school_b.name]))
                    
                    if self.school_matchup_count[matchup_key] >= max_rematches:
                        continue
                    
                    games_to_schedule = []
                    for team_a, team_b, division in matchup.games:
                        if self.team_game_count[team_a.id] < 8 or self.team_game_count[team_b.id] < 8:
                            games_to_schedule.append((team_a, team_b, division))
                    
                    if not games_to_schedule:
                        continue
                    
                    for team_a, team_b, division in games_to_schedule:
                        test_slots = block.get_slots(1)
                        if not test_slots:
                            break
                        
                        slot = test_slots[0]
                        
                        court_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        if court_key in self.used_courts:
                            continue
                        
                        time_slot_key = (slot.date, slot.start_time)
                        if time_slot_key in self.team_time_slots[team_a.id] or time_slot_key in self.team_time_slots[team_b.id]:
                            continue
                        
                        if time_slot_key in self.school_time_slots[team_a.school.name] or time_slot_key in self.school_time_slots[team_b.school.name]:
                            continue
                        
                        if time_slot_key in self.coach_time_slots[team_a.coach_name] or time_slot_key in self.coach_time_slots[team_b.coach_name]:
                            continue
                        
                        if slot.facility.has_8ft_rims and division != Division.ES_K1_REC:
                            continue
                        
                        if division == Division.ES_23_REC:
                            if not self._is_start_or_end_of_day(slot.date, slot.start_time):
                                continue
                        
                        if not self._can_team_play_on_date(team_a, slot.date) or not self._can_team_play_on_date(team_b, slot.date):
                            continue
                        
                        home_school = None
                        if self._facility_belongs_to_school(slot.facility.name, team_a.school.name):
                            home_school = team_a.school
                        elif self._facility_belongs_to_school(slot.facility.name, team_b.school.name):
                            home_school = team_b.school
                        
                        if home_school:
                            if team_a.school == home_school:
                                home_team = team_a
                                away_team = team_b
                            else:
                                home_team = team_b
                                away_team = team_a
                        else:
                            home_team = team_a
                            away_team = team_b
                        
                        game = Game(
                            id=f"{division.value}_{len(schedule.games)}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=division
                        )
                        schedule.games.append(game)
                        
                        self.team_game_count[team_a.id] += 1
                        self.team_game_count[team_b.id] += 1
                        self.team_game_dates[team_a.id].append(slot.date)
                        self.team_game_dates[team_b.id].append(slot.date)
                        
                        self.used_courts.add(court_key)
                        self.team_time_slots[team_a.id].add(time_slot_key)
                        self.team_time_slots[team_b.id].add(time_slot_key)
                        self.school_time_slots[team_a.school.name].add(time_slot_key)
                        self.school_time_slots[team_b.school.name].add(time_slot_key)
                        self.coach_time_slots[team_a.coach_name].add(time_slot_key)
                        self.coach_time_slots[team_b.coach_name].add(time_slot_key)
                        
                        self.school_matchup_count[matchup_key] += 1
                        games_added += 1
                        
                        break
            
            print(f"      Added {games_added} games in this fill pass")
            
            if games_added == 0:
                print(f"      No more games could be added, stopping aggressive fill")
                break
        
        teams_final = [t for t in self.teams if self.team_game_count[t.id] < 8]
        if teams_final:
            print(f"    ⚠️  {len(teams_final)} teams still under 8 games after aggressive fill")
        else:
            print(f"    ✅ ALL teams have 8 games!")

