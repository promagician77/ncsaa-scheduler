"""
Data models for the NCSAA Basketball Scheduling System.
Defines all data structures used throughout the application.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time
from typing import List, Optional, Set, Dict
from enum import Enum


class Division(Enum):
    """Basketball divisions in the league."""
    ES_K1_REC = "ES K-1 REC"
    ES_23_REC = "ES 2-3 REC"
    ES_BOYS_COMP = "ES BOY'S COMP"
    ES_GIRLS_COMP = "ES GIRL'S COMP"
    BOYS_JV = "BOY'S JV"
    GIRLS_JV = "GIRL'S JV"


class Tier(Enum):
    """Competitive tier classifications."""
    TIER_1 = "Tier 1"
    TIER_2 = "Tier 2"
    TIER_3 = "Tier 3"
    TIER_4 = "Tier 4"


class Cluster(Enum):
    """Geographic clusters for schools."""
    EAST = "East"
    WEST = "West"
    NORTH = "North"
    HENDERSON = "Henderson"


@dataclass
class School:
    """Represents a school in the league."""
    name: str
    cluster: Optional[Cluster] = None
    tier: Optional[Tier] = None
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if isinstance(other, School):
            return self.name == other.name
        return False


@dataclass
class Team:
    """Represents a basketball team."""
    id: str
    school: School
    division: Division
    coach_name: str
    coach_email: str
    home_facility: Optional[str] = None
    tier: Optional[Tier] = None
    cluster: Optional[Cluster] = None
    
    # Relationship constraints
    rivals: Set[str] = field(default_factory=set)  # Team IDs that should play each other
    do_not_play: Set[str] = field(default_factory=set)  # Team IDs that should NOT play each other
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, Team):
            return self.id == other.id
        return False


@dataclass
class Facility:
    """Represents a game facility/venue."""
    name: str
    address: str
    available_dates: List[date] = field(default_factory=list)
    unavailable_dates: List[date] = field(default_factory=list)
    max_courts: int = 1
    has_8ft_rims: bool = False  # For ES K-1 REC division
    notes: str = ""
    
    def is_available(self, game_date: date) -> bool:
        """Check if facility is available on a given date."""
        if self.unavailable_dates and game_date in self.unavailable_dates:
            return False
        if self.available_dates:
            return game_date in self.available_dates
        return True
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if isinstance(other, Facility):
            return self.name == other.name
        return False


@dataclass
class TimeSlot:
    """Represents a time slot for a game."""
    date: date
    start_time: time
    end_time: time
    facility: Facility
    court_number: int = 1
    
    def __str__(self):
        return f"{self.date} {self.start_time}-{self.end_time} at {self.facility.name}"
    
    def overlaps_with(self, other: 'TimeSlot') -> bool:
        """Check if this time slot overlaps with another."""
        if self.date != other.date or self.facility != other.facility:
            return False
        if self.court_number != other.court_number:
            return False
        
        # Check time overlap
        return not (self.end_time <= other.start_time or self.start_time >= other.end_time)


@dataclass
class Game:
    """Represents a scheduled game."""
    id: str
    home_team: Team
    away_team: Team
    time_slot: TimeSlot
    division: Division
    is_doubleheader: bool = False
    officials_count: int = 2
    
    def __str__(self):
        return f"{self.away_team.id} @ {self.home_team.id} on {self.time_slot}"
    
    def involves_team(self, team: Team) -> bool:
        """Check if this game involves the given team."""
        return self.home_team == team or self.away_team == team
    
    def get_opponent(self, team: Team) -> Optional[Team]:
        """Get the opponent team for a given team."""
        if self.home_team == team:
            return self.away_team
        elif self.away_team == team:
            return self.home_team
        return None
    
    def is_home_game(self, team: Team) -> bool:
        """Check if this is a home game for the given team."""
        return self.home_team == team


@dataclass
class Schedule:
    """Represents a complete season schedule."""
    games: List[Game] = field(default_factory=list)
    season_start: date = None
    season_end: date = None
    
    def add_game(self, game: Game):
        """Add a game to the schedule."""
        self.games.append(game)
    
    def get_team_games(self, team: Team) -> List[Game]:
        """Get all games for a specific team."""
        return [game for game in self.games if game.involves_team(team)]
    
    def get_games_by_date(self, game_date: date) -> List[Game]:
        """Get all games on a specific date."""
        return [game for game in self.games if game.time_slot.date == game_date]
    
    def get_games_by_facility(self, facility: Facility) -> List[Game]:
        """Get all games at a specific facility."""
        return [game for game in self.games if game.time_slot.facility == facility]
    
    def get_games_by_division(self, division: Division) -> List[Game]:
        """Get all games in a specific division."""
        return [game for game in self.games if game.division == division]


@dataclass
class SchedulingConstraint:
    """Represents a scheduling constraint violation."""
    constraint_type: str
    severity: str  # 'hard' or 'soft'
    description: str
    affected_teams: List[Team] = field(default_factory=list)
    affected_games: List[Game] = field(default_factory=list)
    penalty_score: float = 0.0


@dataclass
class ScheduleValidationResult:
    """Results from validating a schedule."""
    is_valid: bool
    hard_constraint_violations: List[SchedulingConstraint] = field(default_factory=list)
    soft_constraint_violations: List[SchedulingConstraint] = field(default_factory=list)
    total_penalty_score: float = 0.0
    
    def add_violation(self, constraint: SchedulingConstraint):
        """Add a constraint violation to the results."""
        if constraint.severity == 'hard':
            self.hard_constraint_violations.append(constraint)
            self.is_valid = False
        else:
            self.soft_constraint_violations.append(constraint)
        self.total_penalty_score += constraint.penalty_score
    
    def get_summary(self) -> str:
        """Get a summary of validation results."""
        summary = f"Schedule Valid: {self.is_valid}\n"
        summary += f"Hard Violations: {len(self.hard_constraint_violations)}\n"
        summary += f"Soft Violations: {len(self.soft_constraint_violations)}\n"
        summary += f"Total Penalty Score: {self.total_penalty_score:.2f}\n"
        return summary


@dataclass
class TeamScheduleStats:
    """Statistics for a team's schedule."""
    team: Team
    total_games: int = 0
    home_games: int = 0
    away_games: int = 0
    doubleheaders: int = 0
    games_by_week: Dict[int, int] = field(default_factory=dict)
    opponents: List[Team] = field(default_factory=list)
    
    def calculate_balance_score(self) -> float:
        """Calculate how balanced the home/away split is (0.0 = perfect, higher = worse)."""
        if self.total_games == 0:
            return 0.0
        ideal_split = self.total_games / 2.0
        return abs(self.home_games - ideal_split) + abs(self.away_games - ideal_split)
