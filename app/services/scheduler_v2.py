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
    Represents a block of time at a facility with multiple courts.
    This allows multiple games to be played simultaneously.
    """
    facility: Facility
    date: date
    start_time: time
    num_courts: int  # How many courts are available
    duration_minutes: int = GAME_DURATION_MINUTES
    
    def get_slots(self) -> List[TimeSlot]:
        """Get all individual time slots in this block."""
        slots = []
        for court in range(1, self.num_courts + 1):
            end_datetime = datetime.combine(date.min, self.start_time) + timedelta(minutes=self.duration_minutes)
            slots.append(TimeSlot(
                date=self.date,
                start_time=self.start_time,
                end_time=end_datetime.time(),
                facility=self.facility,
                court_number=court
            ))
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
        
        # Group teams by school and division
        self.teams_by_school = self._group_teams_by_school()
        self.teams_by_division = self._group_teams_by_division()
        self.schools = list(self.teams_by_school.keys())
        
        # Generate time blocks (not individual slots)
        self.time_blocks = self._generate_time_blocks()
        
        # Track usage
        self.used_time_blocks = set()  # (date, start_time, facility_name)
        self.team_game_count = defaultdict(int)
        self.team_game_dates = defaultdict(list)  # Track dates for each team
        self.school_matchup_count = defaultdict(int)  # Track how many times schools play
        
        print(f"\nSchool-Based Scheduler initialized:")
        print(f"  Season: {self.season_start} to {self.season_end}")
        print(f"  Teams: {len(self.teams)}")
        print(f"  Schools: {len(self.schools)}")
        print(f"  Facilities: {len(self.facilities)}")
        print(f"  Time blocks: {len(self.time_blocks)}")
    
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
        Generate time blocks (facility + date + time + multiple courts).
        Each block can accommodate multiple simultaneous games.
        """
        blocks = []
        current_date = self.season_start
        
        while current_date <= self.season_end:
            if not self._is_valid_game_date(current_date):
                current_date += timedelta(days=1)
                continue
            
            day_of_week = current_date.weekday()
            
            # Weeknight blocks (Monday-Friday)
            if day_of_week < 5:
                start_time = WEEKNIGHT_START_TIME
                for slot_num in range(WEEKNIGHT_SLOTS):
                    slot_start = datetime.combine(date.min, start_time) + timedelta(minutes=slot_num * GAME_DURATION_MINUTES)
                    
                    if slot_start.time() < WEEKNIGHT_END_TIME:
                        for facility in self.facilities:
                            if facility.is_available(current_date) and facility.max_courts > 0:
                                blocks.append(TimeBlock(
                                    facility=facility,
                                    date=current_date,
                                    start_time=slot_start.time(),
                                    num_courts=facility.max_courts
                                ))
            
            # Saturday blocks
            elif day_of_week == 5:
                current_time = datetime.combine(date.min, SATURDAY_START_TIME)
                end_datetime = datetime.combine(date.min, SATURDAY_END_TIME)
                
                while current_time + timedelta(minutes=GAME_DURATION_MINUTES) <= end_datetime:
                    for facility in self.facilities:
                        if facility.is_available(current_date) and facility.max_courts > 0:
                            blocks.append(TimeBlock(
                                facility=facility,
                                date=current_date,
                                start_time=current_time.time(),
                                num_courts=facility.max_courts
                            ))
                    current_time += timedelta(minutes=GAME_DURATION_MINUTES)
            
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
                            if team_a.school == team_b.school:
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
        """Calculate priority score for a school matchup."""
        score = 0.0
        
        for team_a, team_b, division in games:
            # Same tier is preferred
            if team_a.tier and team_b.tier and team_a.tier == team_b.tier:
                score += PRIORITY_WEIGHTS['tier_matching']
            
            # Same geographic cluster is preferred
            if team_a.cluster and team_b.cluster and team_a.cluster == team_b.cluster:
                score += PRIORITY_WEIGHTS['geographic_cluster']
            
            # Rivals should play
            if team_b.id in team_a.rivals:
                score += PRIORITY_WEIGHTS['respect_rivals']
        
        # Average score across all games in matchup
        return score / len(games) if games else 0
    
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
    
    def _find_time_block_for_matchup(self, matchup: SchoolMatchup) -> Optional[Tuple[TimeBlock, List[TimeSlot]]]:
        """
        Find a time block that can accommodate all games in this school matchup.
        Returns (time_block, assigned_slots) or None if no suitable block found.
        """
        num_games = len(matchup.games)
        
        # Cluster games by coach for optimal ordering
        ordered_games = self._cluster_games_by_coach(matchup.games)
        
        # Try each available time block
        for block in self.time_blocks:
            block_key = (block.date, block.start_time, block.facility.name)
            
            # Skip if block already used
            if block_key in self.used_time_blocks:
                continue
            
            # Check if block has enough courts
            if block.num_courts < num_games:
                continue
            
            # Special handling for ES K-1 REC (needs 8ft rims)
            has_k1_rec = any(div == Division.ES_K1_REC for _, _, div in ordered_games)
            if has_k1_rec and not block.facility.has_8ft_rims:
                continue
            
            # Check if all teams can play on this date
            can_schedule = True
            for team_a, team_b, division in ordered_games:
                # Check game frequency constraints
                if not self._can_team_play_on_date(team_a, block.date):
                    can_schedule = False
                    break
                if not self._can_team_play_on_date(team_b, block.date):
                    can_schedule = False
                    break
            
            if not can_schedule:
                continue
            
            # Check if schools have already played enough times
            matchup_key = tuple(sorted([matchup.school_a.name, matchup.school_b.name]))
            if self.school_matchup_count[matchup_key] >= 2:  # Limit rematches
                continue
            
            # Assign slots
            slots = block.get_slots()
            assigned_slots = slots[:num_games]  # Use first N courts
            
            return (block, assigned_slots)
        
        return None
    
    def _can_team_play_on_date(self, team: Team, game_date: date) -> bool:
        """Check if team can play on this date based on frequency rules."""
        # Check if team already has 8 games
        if self.team_game_count[team.id] >= 8:
            return False
        
        # Check game frequency constraints
        team_dates = self.team_game_dates[team.id]
        
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
        
        # Schedule each matchup
        scheduled_count = 0
        failed_count = 0
        
        for matchup in matchups:
            result = self._find_time_block_for_matchup(matchup)
            
            if result:
                block, assigned_slots = result
                
                # Create games
                for i, (team_a, team_b, division) in enumerate(matchup.games):
                    if i < len(assigned_slots):
                        slot = assigned_slots[i]
                        
                        # Determine home/away based on facility
                        home_team = team_a
                        away_team = team_b
                        if team_b.home_facility and team_b.home_facility == slot.facility.name:
                            home_team = team_b
                            away_team = team_a
                        
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
                
                # Mark block as used
                block_key = (block.date, block.start_time, block.facility.name)
                self.used_time_blocks.add(block_key)
                
                # Track school matchup
                matchup_key = tuple(sorted([matchup.school_a.name, matchup.school_b.name]))
                self.school_matchup_count[matchup_key] += 1
                
                scheduled_count += 1
            else:
                failed_count += 1
        
        print(f"\nScheduling complete:")
        print(f"  Scheduled matchups: {scheduled_count}")
        print(f"  Failed matchups: {failed_count}")
        print(f"  Total games: {len(schedule.games)}")
        
        # Report teams with < 8 games
        teams_under_8 = [t for t in self.teams if self.team_game_count[t.id] < 8]
        if teams_under_8:
            print(f"\n  WARNING: {len(teams_under_8)} teams have < 8 games")
            for team in teams_under_8[:10]:
                print(f"    - {team.school.name} ({team.coach_name}): {self.team_game_count[team.id]} games")
        
        print("=" * 60)
        
        return schedule
