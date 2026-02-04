"""
REDESIGNED Schedule Optimizer - School-Based Clustering
========================================================

This is a complete redesign of the scheduler to properly implement Rule #15:
"Schools should be clustered together by the school name then the coach. 
(We have many coaches that coach multiple divisions in a day). 
This is the most important thing."

KEY CHANGES FROM ORIGINAL:
- Schedules by SCHOOL MATCHUPS instead of by divisions
- All divisions for a school matchup play on the same night
- Coaches with multiple teams have back-to-back games
- Uses time blocks (multiple courts at same facility/time)
"""

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
    GAME_DURATION_MINUTES, WEEKNIGHT_SLOTS,
    MAX_GAMES_PER_7_DAYS, MAX_GAMES_PER_14_DAYS,
    MAX_DOUBLEHEADERS_PER_SEASON, DOUBLEHEADER_BREAK_MINUTES,
    NO_GAMES_ON_SUNDAY, REC_DIVISIONS, ES_K1_REC_PRIORITY_SITES,
    PRIORITY_WEIGHTS
)


@dataclass
class SchoolMatchup:
    """Represents a matchup between two schools across all divisions."""
    school_a: School
    school_b: School
    games: List[Tuple[Team, Team, Division]]  # (team_a, team_b, division)
    priority_score: float = 0.0
    
    def __hash__(self):
        return hash((self.school_a.name, self.school_b.name))


@dataclass
class TimeBlock:
    """
    Represents consecutive time slots on ONE court for back-to-back games.
    
    CRITICAL: This ensures school matchups play back-to-back on the same court.
    Example: Doral Red Rock vs Doral Saddle (3 games):
    - Court 1 at 17:00 (game 1)
    - Court 1 at 18:00 (game 2)  <- SAME COURT, next time slot
    - Court 1 at 19:00 (game 3)  <- SAME COURT, next time slot
    
    NOT: Court 1, 2, 3 all at 17:00 (spread across courts)!
    """
    facility: Facility
    date: date
    start_time: time
    num_consecutive_slots: int  # How many back-to-back slots available
    court_number: int = 1  # Which specific court
    duration_minutes: int = GAME_DURATION_MINUTES
    
    def get_slots(self, num_needed: int = None) -> List[TimeSlot]:
        """
        Get consecutive time slots on the same court for back-to-back games.
        
        Args:
            num_needed: Number of slots needed (defaults to all available)
        """
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
                court_number=self.court_number  # SAME COURT for all slots!
            ))
            current_time = end_datetime.time()
        
        return slots


class SchoolBasedScheduler:
    """
    Redesigned scheduler that groups games by school matchups.
    
    Algorithm:
    1. Identify all unique schools
    2. Generate school matchups (School A vs School B)
    3. For each matchup, find all division games between these schools
    4. Allocate time blocks that can fit all games for a matchup
    5. Cluster coaches within each matchup for back-to-back games
    """
    
    def __init__(self, teams: List[Team], facilities: List[Facility], rules: Dict):
        self.teams = teams
        self.facilities = facilities
        self.rules = rules
        
        # Parse season dates
        self.season_start = self._parse_date(rules.get('season_start', SEASON_START_DATE))
        self.season_end = self._parse_date(rules.get('season_end', SEASON_END_DATE))
        
        # Holidays
        self.holidays = set(rules.get('holidays', []))
        for holiday_str in US_HOLIDAYS:
            self.holidays.add(self._parse_date(holiday_str))
        
        # Blackouts (NEW)
        self.school_blackouts = rules.get('blackouts', {})
        if self.school_blackouts:
            total_blackout_days = sum(len(dates) for dates in self.school_blackouts.values())
            print(f"Loaded {total_blackout_days} blackout dates for {len(self.school_blackouts)} schools")
        
        # Group teams by school and division
        self.teams_by_school = self._group_teams_by_school()
        self.teams_by_division = self._group_teams_by_division()
        self.schools = list(self.teams_by_school.keys())
        
        # Generate time blocks (not individual slots)
        self.time_blocks = self._generate_time_blocks()
        
        # Track usage
        self.used_courts = set()  # (date, start_time, facility_name, court_number) - track individual courts
        self.team_game_count = defaultdict(int)
        self.team_game_dates = defaultdict(list)  # Track dates for each team
        self.school_matchup_count = defaultdict(int)  # Track how many times schools play
        self.team_time_slots = defaultdict(set)  # Track when each team is playing
        self.school_game_dates = defaultdict(list)  # Track dates for each SCHOOL (not just team)
        self.school_time_slots = defaultdict(set)  # Track when each SCHOOL is playing (prevent simultaneous courts)
        self.coach_time_slots = defaultdict(set)  # Track when each COACH is busy (prevent coach conflicts)
        
        # CRITICAL: Track which schools are playing against each other on each court/night
        # Key: (date, facility_name, court_number, school_name) -> opponent_school_name
        # This ensures ALL games for a school on a court/night are against the SAME opponent
        self.school_opponents_on_court = {}  # {(date, facility, court, school): opponent_school}
        
        # CRITICAL: Track which facility each school plays at on each date
        # A school should only play at ONE facility per day
        self.school_facility_dates = {}  # {(school_name, date): facility_name}
        
        # CRITICAL: Track which weeknights each school has been scheduled
        # To prevent spreading schools over multiple weeknights
        # Client: "grouping them together so they only come to the gym 1 night"
        self.school_weeknight_count = defaultdict(int)  # {school_name: count of weeknights}
        self.school_weeknights = defaultdict(set)  # {school_name: set of weeknight dates}
        
        # CRITICAL: Track facility utilization to maximize space usage
        # Client: "If we have a site for 8-10 hours we should have more than 3-4 games there"
        self.facility_date_games = defaultdict(int)  # {(facility_name, date): game_count}
        
        print(f"\nSchool-Based Scheduler initialized:")
        print(f"  Season: {self.season_start} to {self.season_end}")
        print(f"  Teams: {len(self.teams)}")
        print(f"  Schools: {len(self.schools)}")
        print(f"  Facilities: {len(self.facilities)}")
        print(f"  Time blocks: {len(self.time_blocks)}")
        
        # CRITICAL: Check data quality
        self._check_cluster_coverage()
        self._report_data_quality()
    
    def _check_cluster_coverage(self):
        """
        Check what percentage of teams have cluster assignments.
        Warn if coverage is low, as this will severely limit geographic clustering.
        """
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
        """
        Report comprehensive data quality issues.
        Helps identify missing or problematic data before scheduling.
        """
        print(f"\n{'='*80}")
        print("DATA QUALITY REPORT")
        print(f"{'='*80}")
        
        # Get unique schools
        unique_schools = {}
        for team in self.teams:
            if team.school.name not in unique_schools:
                unique_schools[team.school.name] = team.school
        
        # Check tier coverage
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
        
        # Check blackout coverage
        if hasattr(self, 'school_blackouts'):
            schools_with_blackouts = len(self.school_blackouts)
            print(f"\n[BLACKOUT DATA]")
            print(f"  Schools with blackouts: {schools_with_blackouts}")
            if schools_with_blackouts > 0:
                total_blackout_days = sum(len(dates) for dates in self.school_blackouts.values())
                print(f"  Total blackout dates: {total_blackout_days}")
        
        # Check team distribution
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
        
        # Check K-1 facilities
        k1_facilities = [f for f in self.facilities if f.has_8ft_rims]
        print(f"\n[K-1 FACILITIES]")
        print(f"  Facilities with 8ft rims: {len(k1_facilities)}")
        for facility in k1_facilities:
            print(f"    - {facility.name}")
        
        print(f"\n{'='*80}")
        print("DATA QUALITY CHECK COMPLETE")
        print(f"{'='*80}\n")
        
        # DIAGNOSTIC: Show facility availability for first week
        print(f"\n{'='*80}")
        print("FIRST WEEK FACILITY AVAILABILITY (Jan 5-11, 2026)")
        print(f"{'='*80}")
        first_week_dates = [self.season_start + timedelta(days=i) for i in range(7)]
        
        # Check key facilities
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
        """Parse a date from string or date object."""
        if isinstance(date_input, date):
            return date_input
        if isinstance(date_input, str):
            return datetime.strptime(date_input, '%Y-%m-%d').date()
        return date_input
    
    def _group_teams_by_school(self) -> Dict[School, Dict[Division, List[Team]]]:
        """Group teams by school, then by division within each school."""
        groups = defaultdict(lambda: defaultdict(list))
        for team in self.teams:
            groups[team.school][team.division].append(team)
        return dict(groups)
    
    def _group_teams_by_division(self) -> Dict[Division, List[Team]]:
        """Group teams by division."""
        groups = defaultdict(list)
        for team in self.teams:
            groups[team.division].append(team)
        return dict(groups)
    
    def _is_valid_game_date(self, game_date: date) -> bool:
        """Check if a date is valid for scheduling games."""
        if game_date < self.season_start or game_date > self.season_end:
            return False
        if game_date in self.holidays:
            return False
        if NO_GAMES_ON_SUNDAY and game_date.weekday() == 6:
            return False
        return True
    
    def _generate_time_blocks(self) -> List[TimeBlock]:
        """
        Generate time blocks with CONSECUTIVE slots on SAME court for back-to-back games.
        
        CRITICAL: Each block represents consecutive time slots on ONE specific court.
        This allows school matchups to play back-to-back on the same court.
        """
        blocks = []
        current_date = self.season_start
        
        while current_date <= self.season_end:
            if not self._is_valid_game_date(current_date):
                current_date += timedelta(days=1)
                continue
            
            day_of_week = current_date.weekday()
            
            # Determine available time slots for this day
            if day_of_week < 5:  # Weeknight (Monday-Friday)
                time_slots = []
                current_time = WEEKNIGHT_START_TIME
                while current_time < WEEKNIGHT_END_TIME:
                    end_time = (datetime.combine(date.min, current_time) + timedelta(minutes=GAME_DURATION_MINUTES)).time()
                    if end_time <= WEEKNIGHT_END_TIME:
                        time_slots.append(current_time)
                    current_time = end_time
            elif day_of_week == 5:  # Saturday
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
            
            # For each facility and each court, create blocks with consecutive slots
            for facility in self.facilities:
                if facility.max_courts <= 0:
                    continue
                
                # Check facility availability
                if not facility.is_available(current_date):
                    # Log why facility is skipped (only for first week to avoid spam)
                    if current_date <= self.season_start + timedelta(days=7):
                        if facility.unavailable_dates and current_date in facility.unavailable_dates:
                            pass  # Explicitly unavailable
                        elif facility.available_dates and current_date not in facility.available_dates:
                            # Facility has specific dates but this isn't one of them
                            pass
                    continue
                
                # For each court at this facility
                for court_num in range(1, facility.max_courts + 1):
                    # Create blocks starting at each time slot
                    for start_idx, start_time in enumerate(time_slots):
                        # Calculate how many consecutive slots are available from this start time
                        num_consecutive = len(time_slots) - start_idx
                        
                        # Create a block with these consecutive slots
                        # (the block can provide 1 to num_consecutive slots for back-to-back games)
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
        """
        Generate all possible school matchups.
        For each matchup, identify which divisions both schools have teams in.
        """
        matchups = []
        
        for i, school_a in enumerate(self.schools):
            for school_b in self.schools[i + 1:]:
                # CRITICAL: NEVER create same-school matchups (Rule #23)
                if school_a.name == school_b.name:
                    continue
                
                # Find all divisions where both schools have teams
                games_for_matchup = []
                
                # Iterate over all Division enum values
                for division in Division:
                    teams_a = self.teams_by_school[school_a].get(division, [])
                    teams_b = self.teams_by_school[school_b].get(division, [])
                    
                    # Create games between all team combinations in this division
                    for team_a in teams_a:
                        for team_b in teams_b:
                            # CRITICAL: Never match teams from same school (Rule #23)
                            # Use school NAME comparison (not object comparison)
                            if team_a.school.name == team_b.school.name:
                                continue
                            
                            # Skip do-not-play
                            if team_b.id in team_a.do_not_play or team_a.id in team_b.do_not_play:
                                continue
                            
                            games_for_matchup.append((team_a, team_b, division))
                
                if games_for_matchup:
                    # Calculate priority score based on tier/cluster matching
                    score = self._calculate_school_matchup_score(school_a, school_b, games_for_matchup)
                    matchups.append(SchoolMatchup(
                        school_a=school_a,
                        school_b=school_b,
                        games=games_for_matchup,
                        priority_score=score
                    ))
        
        # Sort by priority score (highest first)
        matchups.sort(key=lambda m: m.priority_score, reverse=True)
        
        print(f"\nGenerated {len(matchups)} school matchups")
        return matchups
    
    def _calculate_school_matchup_score(self, school_a: School, school_b: School, 
                                       games: List[Tuple[Team, Team, Division]]) -> float:
        """
        Calculate priority score for a school matchup.
        Higher score = schedule this matchup first.
        
        PRIORITIES (in order):
        1. Home facilities (schools play at their gyms)
        2. Same geographic cluster (minimize travel)
        3. Same tier (competitive balance)
        4. Rivals (required matchups)
        """
        # CRITICAL: NEVER allow same-school matchups (Rule #23)
        # Teams from the same school should NEVER play each other
        if school_a.name == school_b.name:
            return float('-inf')
        
        score = 0.0
        same_cluster_count = 0
        cross_cluster_count = 0
        
        for team_a, team_b, division in games:
            # CRITICAL: Same tier is strongly preferred for competitive balance
            if team_a.tier and team_b.tier:
                if team_a.tier == team_b.tier:
                    score += PRIORITY_WEIGHTS['tier_matching']
                else:
                    # PENALTY for tier mismatches (competitive imbalance)
                    # Tier 1 vs Tier 4 should be heavily penalized
                    tier_diff = abs(int(team_a.tier.value.split()[-1]) - int(team_b.tier.value.split()[-1]))
                    score -= PRIORITY_WEIGHTS['tier_matching'] * tier_diff * 0.5
            
            # CRITICAL: Same geographic cluster is HIGHLY preferred
            # This minimizes travel distance for teams
            # Client: "Everyone should be able to play near their homes" (especially Week 1)
            if team_a.cluster and team_b.cluster:
                if team_a.cluster == team_b.cluster:
                    score += PRIORITY_WEIGHTS['geographic_cluster']
                    same_cluster_count += 1
                else:
                    # MASSIVE PENALTY for cross-cluster matchups (teams traveling across town)
                    # Penalty increases dramatically for early weeks
                    base_penalty = PRIORITY_WEIGHTS['geographic_cluster']
                    
                    # Week-based penalty multiplier:
                    # Week 1: 100x penalty (almost impossible to schedule cross-cluster)
                    # Weeks 2-4: 10x penalty (very strong discouragement)
                    # Later weeks: 2x penalty (moderate discouragement)
                    # Note: We can't calculate exact week here, so use strong penalty always
                    score -= base_penalty * 50  # Very strong penalty
                    cross_cluster_count += 1
            
            # Rivals should play
            if team_b.id in team_a.rivals:
                score += PRIORITY_WEIGHTS['respect_rivals']
        
        # CRITICAL: Huge bonus if either school has a home facility
        # This ensures schools like Faith actually play at their home gyms
        if self._school_has_facility(school_a) or self._school_has_facility(school_b):
            score += 1000  # Very high priority for schools with home facilities
        
        # Additional bonus if ALL games in matchup are same-cluster
        if same_cluster_count > 0 and cross_cluster_count == 0:
            score += 200  # Extra bonus for perfect geographic clustering
        
        # CRITICAL: Prioritize under-utilized facilities (maximize space usage)
        # Client: "If we have a site for 8-10 hours we should have more than 3-4 games there"
        # Check if either school has a facility that's under-utilized
        for school in [school_a, school_b]:
            for facility in self.facilities:
                if self._facility_belongs_to_school(facility.name, school.name):
                    # Count how many games are already at this facility across all dates
                    total_games_at_facility = sum(
                        count for (fac_name, _date), count in self.facility_date_games.items()
                        if fac_name == facility.name
                    )
                    
                    # If facility has < 10 games total, prioritize it
                    # (8-10 hour facility should have 8+ games)
                    if total_games_at_facility < 10:
                        underutil_bonus = (10 - total_games_at_facility) * 10
                        score += underutil_bonus
        
        # Average score across all games in matchup
        return score / len(games) if games else 0
    
    def _school_has_facility(self, school: School) -> bool:
        """Check if a school has a home facility."""
        school_lower = school.name.lower()
        for facility in self.facilities:
            facility_lower = facility.name.lower()
            if school_lower in facility_lower:
                return True
        return False
    
    def _cluster_games_by_coach(self, games: List[Tuple[Team, Team, Division]]) -> List[Tuple[Team, Team, Division]]:
        """
        Cluster games so that coaches with multiple teams have back-to-back games.
        This is critical for Rule #15.
        """
        # Group games by coaches involved
        coach_games = defaultdict(list)
        for game in games:
            team_a, team_b, division = game
            # Track which coaches are in this game
            coaches = set()
            if team_a.coach_name:
                coaches.add(team_a.coach_name)
            if team_b.coach_name:
                coaches.add(team_b.coach_name)
            
            for coach in coaches:
                coach_games[coach].append(game)
        
        # Sort games to cluster by coach
        # Games with same coach should be adjacent
        ordered_games = []
        used_games = set()
        
        # First, add games for coaches with multiple teams (they need clustering)
        for coach, coach_game_list in sorted(coach_games.items(), key=lambda x: -len(x[1])):
            if len(coach_game_list) > 1:
                for game in coach_game_list:
                    game_key = (game[0].id, game[1].id, game[2])
                    if game_key not in used_games:
                        ordered_games.append(game)
                        used_games.add(game_key)
        
        # Then add remaining games
        for game in games:
            game_key = (game[0].id, game[1].id, game[2])
            if game_key not in used_games:
                ordered_games.append(game)
                used_games.add(game_key)
        
        return ordered_games
    
    def _is_start_or_end_of_day(self, game_date: date, start_time: time) -> bool:
        """
        Check if a time slot is at the start or end of the day.
        Used for ES 2-3 REC games (1 ref) which should be at day boundaries.
        """
        day_of_week = game_date.weekday()
        
        # Determine available time slots for this day
        if day_of_week < 5:  # Weeknight (Monday-Friday)
            time_slots = []
            current_time = WEEKNIGHT_START_TIME
            while current_time < WEEKNIGHT_END_TIME:
                end_time = (datetime.combine(date.min, current_time) + timedelta(minutes=GAME_DURATION_MINUTES)).time()
                if end_time <= WEEKNIGHT_END_TIME:
                    time_slots.append(current_time)
                current_time = end_time
        elif day_of_week == 5:  # Saturday
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
        
        # Check if this time is the first or last slot of the day
        return start_time == time_slots[0] or start_time == time_slots[-1]
    
    def _facility_belongs_to_school(self, facility_name: str, school_name: str) -> bool:
        """
        Check if a facility belongs to a school.
        
        CRITICAL: Handles multi-team schools (e.g., Pinecrest Sloan Canyon Blue/Black/White)
        and spelling variations (e.g., "Pincrest" vs "Pinecrest")
        
        Examples:
        - "Faith" school matches "Faith Lutheran" facility
        - "Somerset Sky Pointe" school matches "Somerset Sky Pointe" facility
        - "Pinecrest Sloan Canyon Blue" matches "Pincrest Sloan Canyon" facility (typo!)
        - "Pinecrest Sloan Canyon Black" matches "Pinecrest Sloan Canyon" facility
        """
        # Normalize names for comparison
        facility_lower = facility_name.lower()
        school_lower = school_name.lower()
        
        # Fix common spelling variations/typos
        facility_lower = facility_lower.replace('pincrest', 'pinecrest')
        school_lower = school_lower.replace('pincrest', 'pinecrest')
        
        # Remove team color suffixes for multi-team schools
        # e.g., "Pinecrest Sloan Canyon Blue" -> "Pinecrest Sloan Canyon"
        color_suffixes = [' blue', ' black', ' white', ' red', ' gold', ' silver', ' navy', 
                         ' green', ' purple', ' orange', ' yellow']
        school_base = school_lower
        for suffix in color_suffixes:
            if school_base.endswith(suffix):
                school_base = school_base[:-len(suffix)].strip()
                break
        
        # Also remove number suffixes (e.g., "Faith 6A" -> "Faith")
        import re
        school_base = re.sub(r'\s+\d+[a-z]?$', '', school_base).strip()
        
        # Check if base school name is in facility name
        if school_base in facility_lower:
            return True
        
        # Also check original school name (for exact matches)
        if school_lower in facility_lower:
            return True
        
        return False
    
    def _find_time_block_for_matchup(
        self, 
        matchup: SchoolMatchup,
        relax_saturday_rest: bool = False,
        relax_weeknight_3game: bool = False
    ) -> Optional[Tuple[TimeBlock, List[TimeSlot], School]]:
        """
        Find a time block that can accommodate all games in this school matchup.
        
        CRITICAL (Rule #10): If using a school's facility, that school MUST be the home team.
        
        Returns (time_block, assigned_slots, home_school) or None if no suitable block found.
        """
        num_games = len(matchup.games)
        
        # Cluster games by coach for optimal ordering
        ordered_games = self._cluster_games_by_coach(matchup.games)
        
        # Prioritize blocks: STRONGLY prefer facilities that match one of the schools
        # CRITICAL: Home facilities should ONLY be used by the home school
        home_facility_blocks = []  # Highest priority - home facilities for this matchup
        neutral_blocks = []  # Lower priority - neutral facilities
        
        for block in self.time_blocks:
            # Check if facility belongs to one of the schools IN THIS MATCHUP
            school_a_home = self._facility_belongs_to_school(block.facility.name, matchup.school_a.name)
            school_b_home = self._facility_belongs_to_school(block.facility.name, matchup.school_b.name)
            
            # Check if facility belongs to ANY school (to avoid using other schools' gyms)
            facility_belongs_to_other_school = False
            if not school_a_home and not school_b_home:
                # This facility might belong to a different school
                for team in self.teams:
                    if self._facility_belongs_to_school(block.facility.name, team.school.name):
                        # This facility belongs to a school not in this matchup
                        facility_belongs_to_other_school = True
                        break
            
            if school_a_home:
                # CRITICAL: Prioritize matchups with more games at home facilities
                # Client: "Faith only 1 game instead of 3. Need all 3 games."
                # Strategy: Allow ALL matchups at home facility, but prioritize larger ones
                num_school_a_teams = len([t for t in self.teams if t.school == matchup.school_a])
                num_games = len(matchup.games)
                
                # Calculate priority weight based on game count
                # More games = higher priority for home facility
                if num_games >= num_school_a_teams:
                    # Ideal: Matchup has enough games for all teams
                    weight = 1000 + (num_games * 10)  # Very high priority
                elif num_games >= 3:
                    # Good: At least 3 games (enough for officials)
                    weight = 500 + (num_games * 10)  # High priority
                else:
                    # Acceptable: 1-2 games (can combine multiple matchups to reach 3+)
                    # Still prefer home facility, just lower priority
                    weight = 100 + (num_games * 10)  # Medium priority
                
                home_facility_blocks.append((block, matchup.school_a, weight))
                
            elif school_b_home:
                # CRITICAL: Prioritize matchups with more games at home facilities
                num_school_b_teams = len([t for t in self.teams if t.school == matchup.school_b])
                num_games = len(matchup.games)
                
                # Calculate priority weight based on game count
                if num_games >= num_school_b_teams:
                    # Ideal: Matchup has enough games for all teams
                    weight = 1000 + (num_games * 10)
                elif num_games >= 3:
                    # Good: At least 3 games (enough for officials)
                    weight = 500 + (num_games * 10)
                else:
                    # Acceptable: 1-2 games (can combine multiple matchups to reach 3+)
                    weight = 100 + (num_games * 10)
                
                home_facility_blocks.append((block, matchup.school_b, weight))
            elif not facility_belongs_to_other_school:
                # Only use neutral facilities (not belonging to any school)
                neutral_blocks.append((block, None, 1))  # Neutral facility, weight=1
            # Skip facilities belonging to other schools
        
        # Sort home facility blocks by WEIGHT (highest first), then date
        # This ensures matchups with more games get priority at home facilities
        home_facility_blocks.sort(key=lambda x: (-x[2], x[0].date, x[0].start_time))
        neutral_blocks.sort(key=lambda x: (x[0].date, x[0].start_time))
        
        # Try home facilities FIRST (much higher priority), then neutral
        all_blocks = home_facility_blocks + neutral_blocks
        
        for block, home_school, weight in all_blocks:
            # Check if this block has enough CONSECUTIVE slots for back-to-back games
            if block.num_consecutive_slots < num_games:
                continue
            
            # CRITICAL: STRICT 3-game minimum on ALL weeknight courts (for referees)
            # Client: "on a weeknight we need to use every game slot. We can't have just 1 game 
            # on a night or even 2. We need all 3 slots used. Referees will not come unless 
            # they get 3 games."
            # 
            # RELAXATION: In very late rematch passes (8+), allow <3 games if desperate
            is_weeknight = block.date.weekday() < 5
            if is_weeknight and not relax_weeknight_3game:
                # Count existing games at this facility on this date/court
                existing_games_at_facility = sum(
                    1 for (d, _t, f, c) in self.used_courts
                    if d == block.date and f == block.facility.name and c == block.court_number
                )
                
                total_games_after = existing_games_at_facility + num_games
                
                # STRICT: ALL weeknight courts need 3+ games (NO EXCEPTIONS)
                # This applies to home AND neutral facilities
                if total_games_after < 3:
                    # Skip this block - not enough games for referees
                    continue
            
            # CRITICAL: Prevent schools from spreading over multiple weeknights
            # Client: "grouping them together so they only come to the gym 1 night"
            # If either school already has a weeknight, MUST use that same night
            if is_weeknight:
                school_a_weeknights = self.school_weeknights[matchup.school_a.name]
                school_b_weeknights = self.school_weeknights[matchup.school_b.name]
                
                # If school A already has a weeknight game
                if len(school_a_weeknights) > 0:
                    # This block MUST be on one of school A's existing weeknights
                    if block.date not in school_a_weeknights:
                        continue  # Skip - would create a second weeknight for school A
                
                # If school B already has a weeknight game
                if len(school_b_weeknights) > 0:
                    # This block MUST be on one of school B's existing weeknights
                    if block.date not in school_b_weeknights:
                        continue  # Skip - would create a second weeknight for school B
            
            # Check if the consecutive slots on this court are available
            slots_available = True
            test_slots = block.get_slots(num_games)
            
            for slot in test_slots:
                court_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                if court_key in self.used_courts:
                    slots_available = False
                    break
            
            if not slots_available:
                continue
            
            # Special handling for ES K-1 REC and 8ft rim courts
            has_k1_rec = any(div == Division.ES_K1_REC for _, _, div in ordered_games)
            has_non_k1_rec = any(div != Division.ES_K1_REC for _, _, div in ordered_games)
            
            # Rule: K-1 REC division REQUIRES 8ft rims
            if has_k1_rec and not block.facility.has_8ft_rims:
                continue
            
            # Rule: 8ft rim courts (K-1 courts) can ONLY be used by K-1 REC division
            # CRITICAL: ALL games must be K-1 REC, not just some
            # Middle school games (JV, competitive, 2-3 REC) should NOT use K-1 courts
            if block.facility.has_8ft_rims and has_non_k1_rec:
                continue  # Block if ANY game is non-K-1 REC
            
            # Rule: ES 2-3 REC games (1 ref) should ONLY be at start or end of day
            # This avoids disrupting the 2-ref flow for other divisions
            has_23_rec = any(div == Division.ES_23_REC for _, _, div in ordered_games)
            if has_23_rec:
                if not self._is_start_or_end_of_day(block.date, block.start_time):
                    continue  # ES 2-3 REC must be at day boundaries
            
            # Check if all teams can play on this date and in these time slots
            can_schedule = True
            test_slots = block.get_slots(num_games)
            
            # CRITICAL: Check if either school is already playing at a DIFFERENT facility on this date
            # A school should only play at ONE facility per day (WEEKDAYS ONLY - relax on weekends)
            # Weekends have more games and need flexibility
            if block.date.weekday() < 5:  # Monday-Friday only
                school_a_key = (matchup.school_a.name, block.date)
                school_b_key = (matchup.school_b.name, block.date)
                
                if school_a_key in self.school_facility_dates:
                    if self.school_facility_dates[school_a_key] != block.facility.name:
                        # School A already playing at different facility today
                        can_schedule = False
                
                if school_b_key in self.school_facility_dates:
                    if self.school_facility_dates[school_b_key] != block.facility.name:
                        # School B already playing at different facility today
                        can_schedule = False
                
                if not can_schedule:
                    continue
            
            # CRITICAL: Track which schools are playing in this time block
            # to prevent same school on different courts at same time
            schools_in_block = set()
            
            # CRITICAL: Track teams playing in THIS MATCHUP on THIS DATE
            # to prevent weeknight doubleheaders (same team, 2 games, same night)
            teams_in_matchup_on_date = defaultdict(int)
            
            for i, (team_a, team_b, division) in enumerate(ordered_games):
                if i >= len(test_slots):
                    can_schedule = False
                    break
                
                slot = test_slots[i]
                time_slot_key = (slot.date, slot.start_time)
                
                # CRITICAL: Check if either TEAM is already playing at this specific time
                if time_slot_key in self.team_time_slots[team_a.id]:
                    can_schedule = False
                    break
                if time_slot_key in self.team_time_slots[team_b.id]:
                    can_schedule = False
                    break
                
                # CRITICAL: Check if either SCHOOL is already playing at this specific time
                # This prevents "Pinecrest Springs on different courts at same time"
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
                
                # Track schools in this block
                schools_in_block.add(team_a.school.name)
                schools_in_block.add(team_b.school.name)
                
                # Track teams in this matchup (for weeknight doubleheader check)
                teams_in_matchup_on_date[team_a.id] += 1
                teams_in_matchup_on_date[team_b.id] += 1
                
                # CRITICAL: Check school opponent consistency on same court/night
                # "If a school plays on a weeknight we should have all the games on that court
                # be those 2 schools and not a mix and match of schools."
                # Apply STRICTLY on weeknights at NEUTRAL facilities
                # RELAX at HOME facilities (school can host multiple opponents to reach 3+ games)
                
                is_weeknight = block.date.weekday() < 5
                is_home_facility = self._facility_belongs_to_school(block.facility.name, team_a.school.name) or \
                                   self._facility_belongs_to_school(block.facility.name, team_b.school.name)
                
                # First, check if ANY school is already using this court/night
                court_date_key = (block.date, block.facility.name, block.court_number)
                schools_on_this_court = set()
                for (date, facility, court, school), opponent in self.school_opponents_on_court.items():
                    if date == block.date and facility == block.facility.name and court == block.court_number:
                        schools_on_this_court.add(school)
                        schools_on_this_court.add(opponent)
                
                # If there are already schools on this court/night, check if current matchup matches
                # STRICT enforcement on weeknights at NEUTRAL facilities
                # RELAXED at HOME facilities (allow multiple opponents to reach 3+ games)
                if schools_on_this_court and is_weeknight and not is_home_facility:
                    current_matchup_schools = {team_a.school.name, team_b.school.name}
                    if current_matchup_schools != schools_on_this_court:
                        # Different school matchup trying to use same court/night
                        can_schedule = False
                        break  # Breaks school clustering - court is reserved for other schools
                
                # Also check individual school consistency (original logic)
                court_key_a = (block.date, block.facility.name, block.court_number, team_a.school.name)
                court_key_b = (block.date, block.facility.name, block.court_number, team_b.school.name)
                
                # Check if team_a's school is already playing on this court/night
                if court_key_a in self.school_opponents_on_court:
                    # School A is already playing on this court/night
                    # Ensure opponent is the SAME as before
                    expected_opponent = self.school_opponents_on_court[court_key_a]
                    if expected_opponent != team_b.school.name:
                        can_schedule = False
                        break  # Different opponent - breaks school clustering
                
                # Check if team_b's school is already playing on this court/night
                if court_key_b in self.school_opponents_on_court:
                    # School B is already playing on this court/night
                    # Ensure opponent is the SAME as before
                    expected_opponent = self.school_opponents_on_court[court_key_b]
                    if expected_opponent != team_a.school.name:
                        can_schedule = False
                        break  # Different opponent - breaks school clustering
                
                # CRITICAL: Check weeknight doubleheader constraint
                # A team should NOT play 2+ games on the same weeknight
                if block.date.weekday() < 5:  # Weeknight (Monday-Friday)
                    # Check if this team already has a game on this date (from previous matchups)
                    if block.date in self.team_game_dates[team_a.id]:
                        can_schedule = False
                        break
                    if block.date in self.team_game_dates[team_b.id]:
                        can_schedule = False
                        break
                    
                    # Check if this team will have 2+ games in THIS matchup on this weeknight
                    if teams_in_matchup_on_date[team_a.id] > 1:
                        can_schedule = False
                        break
                    if teams_in_matchup_on_date[team_b.id] > 1:
                        can_schedule = False
                        break
                
                # CRITICAL: Check Saturday doubleheader rest time (non-rec divisions only)
                # "When we do a doubleheader we want an hour in between games in all non-rec divisions.
                # This should only happen on Saturday's."
                # RELAXATION: In later rematch passes, allow shorter rest to fill slots
                if block.date.weekday() == 5 and not relax_saturday_rest:  # Saturday (strict mode)
                    # Check if this is a non-rec division
                    is_rec_division = (division == Division.ES_K1_REC or division == Division.ES_23_REC)
                    
                    if not is_rec_division:
                        # For non-rec divisions, check if team has enough rest time between games
                        # Need at least 1 hour (60 minutes) between games
                        from datetime import datetime
                        
                        # CRITICAL FIX: Check against BOTH already-scheduled games AND games in current block
                        # Collect all time slots for this team on this Saturday (existing + current block)
                        team_a_saturday_times = []
                        team_b_saturday_times = []
                        
                        # Add existing scheduled games (all existing games, we'll check time diff)
                        # Note: We can't easily check if existing games are rec/non-rec from team_time_slots
                        # So we check ALL existing games and enforce 60min gap
                        for existing_time_key in self.team_time_slots[team_a.id]:
                            existing_date, existing_time = existing_time_key
                            if existing_date == block.date:
                                team_a_saturday_times.append(existing_time)
                        
                        for existing_time_key in self.team_time_slots[team_b.id]:
                            existing_date, existing_time = existing_time_key
                            if existing_date == block.date:
                                team_b_saturday_times.append(existing_time)
                        
                        # Add games from CURRENT block that we're evaluating (before this slot)
                        for j in range(i):  # Check all previous games in this block
                            prev_team_a, prev_team_b, prev_div = ordered_games[j]
                            prev_slot = test_slots[j]
                            
                            # Only check non-rec games for rest time
                            prev_is_rec = (prev_div == Division.ES_K1_REC or prev_div == Division.ES_23_REC)
                            if prev_is_rec:
                                continue  # Skip rec games - they don't need rest time
                            
                            if prev_team_a.id == team_a.id or prev_team_b.id == team_a.id:
                                team_a_saturday_times.append(prev_slot.start_time)
                            if prev_team_a.id == team_b.id or prev_team_b.id == team_b.id:
                                team_b_saturday_times.append(prev_slot.start_time)
                        
                        # Check team_a: ensure 60+ minutes from all other non-rec games
                        for existing_time in team_a_saturday_times:
                            existing_datetime = datetime.combine(block.date, existing_time)
                            new_datetime = datetime.combine(block.date, slot.start_time)
                            time_diff_minutes = abs((new_datetime - existing_datetime).total_seconds() / 60)
                            
                            # Need at least 60 minutes between games
                            # "an hour in between" means 60+ minutes gap between END of game 1 and START of game 2
                            # But we're comparing START times, so if games are 1 hour long:
                            # Game 1: 9:00-10:00, Game 2: 10:00-11:00 = 0 min gap (bad)
                            # Game 1: 9:00-10:00, Game 2: 11:00-12:00 = 60 min gap (good)
                            # So we need time_diff >= 120 minutes (2 hours) between START times for 1-hour games
                            if time_diff_minutes < 120:  # Need 2 hours between start times for 60min rest
                                can_schedule = False
                                print(f"      [SATURDAY REST] Blocked: {team_a.school.name} would have {time_diff_minutes:.0f}min between starts (need 120+ for 60min rest)")
                                break
                        
                        # Check team_b: ensure 60+ minutes from all other non-rec games
                        if can_schedule:
                            for existing_time in team_b_saturday_times:
                                existing_datetime = datetime.combine(block.date, existing_time)
                                new_datetime = datetime.combine(block.date, slot.start_time)
                                time_diff_minutes = abs((new_datetime - existing_datetime).total_seconds() / 60)
                                
                                # Need at least 120 minutes between start times (= 60min rest after 1-hour game)
                                if time_diff_minutes < 120:
                                    can_schedule = False
                                    print(f"      [SATURDAY REST] Blocked: {team_b.school.name} would have {time_diff_minutes:.0f}min between starts (need 120+ for 60min rest)")
                                    break
                
                if not can_schedule:
                    break
                
                # Check game frequency constraints (check for each team)
                if not self._can_team_play_on_date(team_a, block.date):
                    can_schedule = False
                    break
                if not self._can_team_play_on_date(team_b, block.date):
                    can_schedule = False
                    break
            
            if not can_schedule:
                continue
            
            # CRITICAL: Verify this is a proper school matchup (2 schools only)
            # If more than 2 schools, it means we're mixing matchups - reject this
            if len(schools_in_block) > 2:
                continue
            
            # Check if schools have already played enough times
            matchup_key = tuple(sorted([matchup.school_a.name, matchup.school_b.name]))
            # Allow up to 2 matchups in first pass, more in rematch pass
            if self.school_matchup_count[matchup_key] >= 2:
                continue
            
            # Get consecutive slots on the same court for back-to-back games
            slots = block.get_slots(num_games)
            
            return (block, slots, home_school)
        
        return None
    
    def _can_team_play_on_date(self, team: Team, game_date: date) -> bool:
        """
        Check if team can play on this date based on frequency rules.
        
        CRITICAL RULES:
        - No doubleheaders on weeknights (Monday-Friday) - PER TEAM
        - Avoid back-to-back days (especially Friday + Saturday) - PER SCHOOL
        - Max 2 games in 7 days - PER TEAM
        - Max 3 games in 14 days - PER TEAM
        - Respect school blackout dates (NEW)
        """
        # Check if team already has 8 games
        if self.team_game_count[team.id] >= 8:
            return False
        
        # NEW: Check school blackout dates
        if hasattr(self, 'school_blackouts') and team.school.name in self.school_blackouts:
            if game_date in self.school_blackouts[team.school.name]:
                return False
        
        # Check game frequency constraints for THIS TEAM
        team_dates = self.team_game_dates[team.id]
        
        # CRITICAL: No doubleheaders on weeknights (per team)
        if game_date.weekday() < 5:  # Monday-Friday (weeknight)
            if game_date in team_dates:
                # Team already has a game on this weeknight
                return False
        
        # CRITICAL: Check SCHOOL-level back-to-back days
        # This prevents Somerset NLV (Stanley) on Friday + Somerset NLV (Lide) on Saturday
        school_dates = self.school_game_dates[team.school.name]
        
        for existing_date in school_dates:
            days_diff = abs((game_date - existing_date).days)
            
            # CRITICAL: Avoid back-to-back days at SCHOOL level (not just team)
            if days_diff == 1:
                # Check if Friday + Saturday
                if (existing_date.weekday() == 4 and game_date.weekday() == 5) or \
                   (existing_date.weekday() == 5 and game_date.weekday() == 4):
                    # School already has a game on consecutive day
                    return False
        
        # Check team-level frequency constraints
        for existing_date in team_dates:
            days_diff = abs((game_date - existing_date).days)
            
            # Max 2 games in 7 days
            if days_diff < 7:
                games_in_7_days = sum(1 for d in team_dates if abs((d - game_date).days) < 7)
                if games_in_7_days >= 2:
                    return False
            
            # Max 3 games in 14 days
            if days_diff < 14:
                games_in_14_days = sum(1 for d in team_dates if abs((d - game_date).days) < 14)
                if games_in_14_days >= 3:
                    return False
        
        return True
    
    def optimize_schedule(self) -> Schedule:
        """
        Main entry point: Generate schedule by school matchups.
        """
        print("\n" + "=" * 60)
        print("SCHOOL-BASED SCHEDULING (Redesigned Algorithm)")
        print("=" * 60)
        
        schedule = Schedule(
            season_start=self.season_start,
            season_end=self.season_end
        )
        
        # Generate all school matchups
        matchups = self._generate_school_matchups()
        
        # Sort matchups by score (higher score = better matchup, schedule first)
        # This ensures high-priority matchups (with home facilities) get scheduled first
        matchups_with_scores = [(m, self._calculate_school_matchup_score(m.school_a, m.school_b, m.games)) for m in matchups]
        matchups_with_scores.sort(key=lambda x: x[1], reverse=True)  # Highest score first
        matchups = [m for m, score in matchups_with_scores]
        
        print(f"\nScheduling {len(matchups)} matchups (sorted by priority)...")
        print(f"  Top priority: Schools with home facilities (score boost: +1000)")
        print(f"  High priority: Rivals, same cluster, same tier")
        
        # Schedule each matchup
        scheduled_count = 0
        failed_count = 0
        
        for matchup in matchups:
            result = self._find_time_block_for_matchup(matchup)
            
            if result:
                block, assigned_slots, home_school = result
                
                # CRITICAL: Check if we have enough slots for ALL games in matchup
                # Client: "would like to see a school have all of their divisions play together on 1 court"
                # Strategy:
                # 1. Prefer scheduling COMPLETE matchups on ONE court
                # 2. Only allow partial matchups as last resort (and track for completion on same court)
                is_weeknight = block.date.weekday() < 5
                is_home_facility = home_school is not None
                
                if len(assigned_slots) < len(matchup.games):
                    # Not enough consecutive slots on this court for all games
                    # STRICT: Do NOT allow partial matchups - find a different block with more slots
                    # This ensures all divisions of a matchup play together on ONE court
                    failed_count += 1
                    continue
                
                # Create games
                for i, (team_a, team_b, division) in enumerate(matchup.games):
                    if i < len(assigned_slots):
                        slot = assigned_slots[i]
                        
                        # CRITICAL: Determine home/away based on home_school (Rule #10)
                        # If facility belongs to a school, that school is ALWAYS the home team
                        if home_school:
                            # One of the schools is the home team (playing at their facility)
                            if team_a.school == home_school:
                                home_team = team_a
                                away_team = team_b
                            else:
                                home_team = team_b
                                away_team = team_a
                        else:
                            # Neutral facility - default to team_a as home
                            home_team = team_a
                            away_team = team_b
                        
                        # CRITICAL: K-1 Court Validation (POST-CHECK)
                        # NEVER allow non-K-1 REC divisions on 8ft rim courts
                        if slot.facility.has_8ft_rims and division != Division.ES_K1_REC:
                            print(f"    [K-1 VIOLATION PREVENTED] {division.value} attempted on {slot.facility.name}")
                            continue  # Skip this game - K-1 court violation
                        
                        game = Game(
                            id=f"{division.value}_{len(schedule.games)}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=division
                        )
                        
                        schedule.add_game(game)
                        
                        # Update tracking
                        self.team_game_count[team_a.id] += 1
                        self.team_game_count[team_b.id] += 1
                        self.team_game_dates[team_a.id].append(block.date)
                        self.team_game_dates[team_b.id].append(block.date)
                        
                        # CRITICAL: Track school-level dates for back-to-back day checking
                        # This prevents Somerset NLV (Stanley) Friday + Somerset NLV (Lide) Saturday
                        if block.date not in self.school_game_dates[team_a.school.name]:
                            self.school_game_dates[team_a.school.name].append(block.date)
                        if block.date not in self.school_game_dates[team_b.school.name]:
                            self.school_game_dates[team_b.school.name].append(block.date)
                        
                        # Mark this specific court as used
                        court_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        self.used_courts.add(court_key)
                        
                        # Track team time slots to prevent double-booking
                        time_slot_key = (slot.date, slot.start_time)
                        self.team_time_slots[team_a.id].add(time_slot_key)
                        self.team_time_slots[team_b.id].add(time_slot_key)
                        
                        # CRITICAL: Track school time slots to prevent same school on different courts
                        self.school_time_slots[team_a.school.name].add(time_slot_key)
                        self.school_time_slots[team_b.school.name].add(time_slot_key)
                        
                        # CRITICAL: Track coach time slots to prevent coach conflicts
                        self.coach_time_slots[team_a.coach_name].add(time_slot_key)
                        self.coach_time_slots[team_b.coach_name].add(time_slot_key)
                        
                        # CRITICAL: Track school opponents on this court/night
                        # This ensures ALL games for a school on a court/night are against SAME opponent
                        school_court_key_a = (slot.date, slot.facility.name, slot.court_number, team_a.school.name)
                        school_court_key_b = (slot.date, slot.facility.name, slot.court_number, team_b.school.name)
                        self.school_opponents_on_court[school_court_key_a] = team_b.school.name
                        self.school_opponents_on_court[school_court_key_b] = team_a.school.name
                        
                        # CRITICAL: Track school-facility-date to prevent school at multiple facilities per day
                        school_date_key_a = (team_a.school.name, slot.date)
                        school_date_key_b = (team_b.school.name, slot.date)
                        self.school_facility_dates[school_date_key_a] = slot.facility.name
                        self.school_facility_dates[school_date_key_b] = slot.facility.name
                        
                        # CRITICAL: Track school weeknight usage to prevent spreading over multiple nights
                        if slot.date.weekday() < 5:  # Weeknight
                            self.school_weeknights[team_a.school.name].add(slot.date)
                            self.school_weeknights[team_b.school.name].add(slot.date)
                        
                        # Track facility utilization
                        facility_date_key = (slot.facility.name, slot.date)
                        self.facility_date_games[facility_date_key] += 1
                
                # Track school matchup
                matchup_key = tuple(sorted([matchup.school_a.name, matchup.school_b.name]))
                self.school_matchup_count[matchup_key] += 1
                
                scheduled_count += 1
            else:
                failed_count += 1
        
        print(f"\nFirst pass complete:")
        print(f"  Scheduled matchups: {scheduled_count}")
        print(f"  Failed matchups: {failed_count}")
        print(f"  Total games: {len(schedule.games)}")
        
        # Check teams with < 8 games
        teams_under_8 = [t for t in self.teams if self.team_game_count[t.id] < 8]
        if teams_under_8:
            print(f"\n  {len(teams_under_8)} teams have < 8 games, starting rematch pass...")
            
            # SECOND PASS: Allow rematches to fill remaining games
            self._schedule_rematches(schedule, matchups, teams_under_8)
            
            # Recheck teams with < 8 games
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
        """
        Second pass: Allow rematches (schools playing 2nd+ time) for teams with < 8 games.
        Progressively relaxes constraints to ensure all teams get 8 games.
        
        Constraint Relaxation Strategy:
        - Pass 1-2: Strict (complete matchups, single facility, court reservation)
        - Pass 3-4: Allow partial matchups
        - Pass 5-6: Allow multiple facilities per day
        - Pass 7-8: Allow mixed matchups on courts
        - Pass 9-10: Desperate fill (minimal constraints)
        """
        print("\n  Starting rematch pass to fill remaining games...")
        print("  Progressive constraint relaxation to ensure 8 games per team")
        
        max_passes = 10
        for pass_num in range(max_passes):
            teams_still_needing = [t for t in self.teams if self.team_game_count[t.id] < 8]
            if not teams_still_needing:
                break
            
            # Determine constraint relaxation level
            allow_partial_matchups = pass_num >= 2  # Pass 3+
            allow_multiple_facilities = pass_num >= 4  # Pass 5+
            allow_mixed_courts = pass_num >= 6  # Pass 7+
            relax_saturday_rest = pass_num >= 3  # Pass 4+ (allow shorter rest on Saturdays)
            relax_weeknight_3game = pass_num >= 7  # Pass 8+ (allow <3 games on weeknights if desperate)
            
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
            
            # Try to schedule matchups for teams that need games
            for matchup in matchups:
                matchup_key = tuple(sorted([matchup.school_a.name, matchup.school_b.name]))
                
                # Check if any teams in this matchup need more games
                teams_in_matchup_need_games = False
                for team_a, team_b, division in matchup.games:
                    if self.team_game_count[team_a.id] < 8 or self.team_game_count[team_b.id] < 8:
                        teams_in_matchup_need_games = True
                        break
                
                if not teams_in_matchup_need_games:
                    continue
                
                # Progressively relax rematch limit
                max_rematches = 2 + pass_num  # Start at 2, increase each pass
                if self.school_matchup_count[matchup_key] >= max_rematches:
                    continue
                
                # Try to schedule this matchup again (with relaxed constraints)
                result = self._find_time_block_for_matchup(
                    matchup,
                    relax_saturday_rest=relax_saturday_rest,
                    relax_weeknight_3game=relax_weeknight_3game
                )
            
            if result:
                block, assigned_slots, home_school = result
                
                # CRITICAL: Check if we need to schedule this matchup
                # Only schedule if at least one team needs games
                teams_need_games = any(
                    self.team_game_count[team_a.id] < 8 or self.team_game_count[team_b.id] < 8
                    for team_a, team_b, division in matchup.games
                )
                
                if not teams_need_games:
                    continue
                
                # CRITICAL: Check if we have enough slots
                # Pass 1-2: Require ALL games (strict)
                # Pass 3+: Allow partial matchups (relaxed)
                if not allow_partial_matchups:
                    # Strict: Need ALL games
                    if len(assigned_slots) < len(matchup.games):
                        continue
                else:
                    # Relaxed: Schedule whatever fits
                    if len(assigned_slots) == 0:
                        continue
                
                # Create games
                for i, (team_a, team_b, division) in enumerate(matchup.games):
                    # Only schedule if at least one team needs games
                    if self.team_game_count[team_a.id] >= 8 and self.team_game_count[team_b.id] >= 8:
                        continue
                    
                    if i < len(assigned_slots):
                        slot = assigned_slots[i]
                        
                        # Determine home/away based on home_school
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
                        
                        # CRITICAL: K-1 Court Validation (POST-CHECK - REMATCH PASS)
                        # NEVER allow non-K-1 REC divisions on 8ft rim courts
                        if slot.facility.has_8ft_rims and division != Division.ES_K1_REC:
                            print(f"    [K-1 VIOLATION PREVENTED - REMATCH] {division.value} attempted on {slot.facility.name}")
                            continue  # Skip this game - K-1 court violation
                        
                        game = Game(
                            id=f"{division.value}_{len(schedule.games)}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=division
                        )
                        
                        schedule.add_game(game)
                        
                        # Update tracking
                        self.team_game_count[team_a.id] += 1
                        self.team_game_count[team_b.id] += 1
                        self.team_game_dates[team_a.id].append(block.date)
                        self.team_game_dates[team_b.id].append(block.date)
                        
                        # CRITICAL: Track school-level dates for back-to-back day checking
                        # This prevents Somerset NLV (Stanley) Friday + Somerset NLV (Lide) Saturday
                        if block.date not in self.school_game_dates[team_a.school.name]:
                            self.school_game_dates[team_a.school.name].append(block.date)
                        if block.date not in self.school_game_dates[team_b.school.name]:
                            self.school_game_dates[team_b.school.name].append(block.date)
                        
                        # Mark this specific court as used
                        court_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        self.used_courts.add(court_key)
                        
                        # Track team time slots to prevent double-booking
                        time_slot_key = (slot.date, slot.start_time)
                        self.team_time_slots[team_a.id].add(time_slot_key)
                        self.team_time_slots[team_b.id].add(time_slot_key)
                        
                        # CRITICAL: Track school time slots to prevent same school on different courts
                        self.school_time_slots[team_a.school.name].add(time_slot_key)
                        self.school_time_slots[team_b.school.name].add(time_slot_key)
                        
                        # CRITICAL: Track coach time slots to prevent coach conflicts
                        self.coach_time_slots[team_a.coach_name].add(time_slot_key)
                        self.coach_time_slots[team_b.coach_name].add(time_slot_key)
                        
                        # CRITICAL: Track school opponents on this court/night
                        # This ensures ALL games for a school on a court/night are against SAME opponent
                        school_court_key_a = (slot.date, slot.facility.name, slot.court_number, team_a.school.name)
                        school_court_key_b = (slot.date, slot.facility.name, slot.court_number, team_b.school.name)
                        self.school_opponents_on_court[school_court_key_a] = team_b.school.name
                        self.school_opponents_on_court[school_court_key_b] = team_a.school.name
                        
                        # CRITICAL: Track school-facility-date to prevent school at multiple facilities per day
                        school_date_key_a = (team_a.school.name, slot.date)
                        school_date_key_b = (team_b.school.name, slot.date)
                        self.school_facility_dates[school_date_key_a] = slot.facility.name
                        self.school_facility_dates[school_date_key_b] = slot.facility.name
                        
                        # CRITICAL: Track school weeknight usage to prevent spreading over multiple nights
                        if slot.date.weekday() < 5:  # Weeknight
                            self.school_weeknights[team_a.school.name].add(slot.date)
                            self.school_weeknights[team_b.school.name].add(slot.date)
                        
                        # Track facility utilization
                        facility_date_key = (slot.facility.name, slot.date)
                        self.facility_date_games[facility_date_key] += 1
                
                # Track school matchup
                self.school_matchup_count[matchup_key] += 1
                games_added += 1
            
            if games_added == 0:
                print(f"    No more games could be scheduled, stopping")
                break
        
        print(f"  Rematch pass complete: {len(schedule.games)} total games")
        
        # CRITICAL: AGGRESSIVE SATURDAY SLOT FILLING
        # Client: "If we have a site for 8-10 hours we should have more than 3-4 games there"
        # Fill ALL available Saturday slots to maximize facility utilization
        teams_still_needing = [t for t in self.teams if self.team_game_count[t.id] < 8]
        if teams_still_needing:
            print(f"\n  AGGRESSIVE SATURDAY FILLING: {len(teams_still_needing)} teams still need games")
            self._fill_saturday_slots_aggressively(schedule, matchups, teams_still_needing)
    
    def _fill_saturday_slots_aggressively(self, schedule: Schedule, matchups: List[SchoolMatchup], teams_needing_games: List[Team]):
        """
        Ultra-aggressive pass to fill ALL available Saturday slots.
        
        Strategy:
        - Ignore 120-min rest requirement (allow back-to-back)
        - Ignore complete matchup requirement (allow ANY partial matchup)
        - Ignore court reservation (allow mixed matchups on same court)
        - ONLY respect HARD constraints (no double-booking, no same-school, etc.)
        
        Goal: Use EVERY available slot at EVERY facility to maximize games.
        """
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
            
            # Increase rematch limit progressively
            max_rematches = 5 + fill_pass
            
            # Try all Saturday time blocks
            saturday_blocks = [b for b in self.time_blocks if b.date.weekday() == 5]
            
            for block in saturday_blocks:
                # For each matchup, try to schedule ANY game from it
                for matchup in matchups:
                    matchup_key = tuple(sorted([matchup.school_a.name, matchup.school_b.name]))
                    
                    # Check rematch limit
                    if self.school_matchup_count[matchup_key] >= max_rematches:
                        continue
                    
                    # Find teams in this matchup that need games
                    games_to_schedule = []
                    for team_a, team_b, division in matchup.games:
                        if self.team_game_count[team_a.id] < 8 or self.team_game_count[team_b.id] < 8:
                            games_to_schedule.append((team_a, team_b, division))
                    
                    if not games_to_schedule:
                        continue
                    
                    # Try to schedule ANY game (even just 1) from this matchup in this block
                    for team_a, team_b, division in games_to_schedule:
                        # Check if we have an available slot
                        test_slots = block.get_slots(1)  # Just need 1 slot
                        if not test_slots:
                            break
                        
                        slot = test_slots[0]
                        
                        # Check if slot is available
                        court_key = (slot.date, slot.start_time, slot.facility.name, slot.court_number)
                        if court_key in self.used_courts:
                            continue
                        
                        # HARD CONSTRAINTS ONLY (no soft constraints)
                        # 1. No team double-booking
                        time_slot_key = (slot.date, slot.start_time)
                        if time_slot_key in self.team_time_slots[team_a.id] or time_slot_key in self.team_time_slots[team_b.id]:
                            continue
                        
                        # 2. No same school at same time (different courts)
                        if time_slot_key in self.school_time_slots[team_a.school.name] or time_slot_key in self.school_time_slots[team_b.school.name]:
                            continue
                        
                        # 3. No coach conflicts
                        if time_slot_key in self.coach_time_slots[team_a.coach_name] or time_slot_key in self.coach_time_slots[team_b.coach_name]:
                            continue
                        
                        # 4. K-1 court restriction
                        if slot.facility.has_8ft_rims and division != Division.ES_K1_REC:
                            continue
                        
                        # 5. ES 2-3 REC timing (start or end of day)
                        if division == Division.ES_23_REC:
                            if not self._is_start_or_end_of_day(slot.date, slot.start_time):
                                continue
                        
                        # 6. Friday + Saturday back-to-back (school-level)
                        if not self._can_team_play_on_date(team_a, slot.date) or not self._can_team_play_on_date(team_b, slot.date):
                            continue
                        
                        # ALL HARD CONSTRAINTS PASSED - SCHEDULE THE GAME!
                        
                        # Determine home/away (prefer home school if facility matches)
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
                        
                        # Create game
                        game = Game(
                            id=f"{division.value}_{len(schedule.games)}",
                            home_team=home_team,
                            away_team=away_team,
                            time_slot=slot,
                            division=division
                        )
                        schedule.games.append(game)
                        
                        # Update tracking
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
                        
                        # Stop after scheduling one game from this matchup (move to next matchup)
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

