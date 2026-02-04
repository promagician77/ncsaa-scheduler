"""
API routes for schedule generation and management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from celery.result import AsyncResult

from app.services.sheets_reader import SheetsReader
from app.services.scheduler import ScheduleOptimizer
from app.services.scheduler_v2 import SchoolBasedScheduler  # New school-based clustering algorithm  # NEW: School-based scheduler
from app.services.validator import ScheduleValidator
from app.models import Game, Division
from app.core.config import (
    SEASON_START_DATE, SEASON_END_DATE,
    WEEKNIGHT_START_TIME, WEEKNIGHT_END_TIME,
    SATURDAY_START_TIME, SATURDAY_END_TIME,
    GAME_DURATION_MINUTES, WEEKNIGHT_SLOTS,
    MAX_GAMES_PER_7_DAYS, MAX_GAMES_PER_14_DAYS,
    MAX_DOUBLEHEADERS_PER_SEASON, DOUBLEHEADER_BREAK_MINUTES,
    NO_GAMES_ON_SUNDAY, US_HOLIDAYS,
    DIVISIONS, REC_DIVISIONS, TIERS, CLUSTERS,
    ES_K1_REC_RIM_HEIGHT, ES_K1_REC_OFFICIALS, ES_K1_REC_PRIORITY_SITES,
    PRIORITY_WEIGHTS
)
from app.core.celery_app import celery_app
from app.tasks.scheduler_tasks import generate_schedule_task


router = APIRouter(prefix="/api", tags=["schedule"])


class ScheduleRequest(BaseModel):
    """Request model for schedule generation."""
    force_regenerate: bool = False


class GameResponse(BaseModel):
    """Response model for a single game."""
    id: str
    home_team: str
    away_team: str
    date: str
    day: str  # Day of week (Monday, Tuesday, etc.)
    time: str
    facility: str
    court: int
    division: str


class ScheduleResponse(BaseModel):
    """Response model for schedule generation."""
    success: bool
    message: str
    total_games: int
    games: List[GameResponse]
    validation: Dict
    generation_time: float


class ScheduleStats(BaseModel):
    """Statistics about the schedule."""
    total_teams: int
    total_games: int
    games_by_division: Dict[str, int]
    teams_with_8_games: int
    teams_under_8_games: int
    teams_over_8_games: int


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.post("/schedule/async")
async def generate_schedule_async(request: ScheduleRequest):
    """
    Start async schedule generation task.
    
    Returns:
        dict: Task ID for polling status
    """
    try:
        # Start Celery task
        task = generate_schedule_task.delay()
        
        return {
            "task_id": task.id,
            "status": "PENDING",
            "message": "Schedule generation started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start task: {str(e)}")


@router.get("/schedule/status/{task_id}")
async def get_schedule_status(task_id: str):
    """
    Get status of async schedule generation task.
    
    Args:
        task_id: Celery task ID
        
    Returns:
        dict: Task status and result (if complete)
    """
    try:
        task_result = AsyncResult(task_id, app=celery_app)
        
        if task_result.state == "PENDING":
            response = {
                "task_id": task_id,
                "status": "PENDING",
                "message": "Task is waiting to start..."
            }
        elif task_result.state == "PROGRESS":
            response = {
                "task_id": task_id,
                "status": "PROGRESS",
                "message": task_result.info.get("status", "Processing...")
            }
        elif task_result.state == "SUCCESS":
            result = task_result.result
            response = {
                "task_id": task_id,
                "status": "SUCCESS",
                "result": result
            }
        elif task_result.state == "FAILURE":
            response = {
                "task_id": task_id,
                "status": "FAILURE",
                "message": str(task_result.info)
            }
        else:
            response = {
                "task_id": task_id,
                "status": task_result.state,
                "message": f"Task state: {task_result.state}"
            }
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@router.post("/schedule", response_model=ScheduleResponse)
async def generate_schedule(request: ScheduleRequest):
    """
    Generate a new basketball schedule.
    
    This endpoint:
    1. Loads data from Google Sheets
    2. Generates an optimized schedule
    3. Validates the schedule
    4. Returns the schedule data
    """
    try:
        start_time = datetime.now()
        
        # Load data from Google Sheets
        print("Loading data from Google Sheets...")
        reader = SheetsReader()
        teams, facilities, rules = reader.load_all_data()
        
        # Generate schedule using NEW school-based algorithm
        print(f"Generating schedule for {len(teams)} teams...")
        print("Using REDESIGNED school-based scheduler (groups by schools, not divisions)")
        optimizer = SchoolBasedScheduler(teams, facilities, rules)  # NEW SCHEDULER
        schedule = optimizer.optimize_schedule()
        
        # Validate schedule
        print("Validating schedule...")
        validator = ScheduleValidator()
        validation_result = validator.validate_schedule(schedule)
        
        # Convert games to response format
        games_response = []
        for game in schedule.games:
            # Format team names with coach names in parentheses
            home_team_display = f"{game.home_team.school.name} ({game.home_team.coach_name})"
            away_team_display = f"{game.away_team.school.name} ({game.away_team.coach_name})"
            
            # Format facility with specific court
            facility_display = game.time_slot.facility.name
            if game.time_slot.court_number and game.time_slot.court_number > 0:
                facility_display = f"{facility_display} - Court {game.time_slot.court_number}"
            
            # Format date and day (matching Google Sheets format)
            date_str = game.time_slot.date.strftime("%Y-%m-%d")
            day_str = game.time_slot.date.strftime("%A")  # Full day name (Monday, Tuesday, etc.)
            
            # Format time in 12-hour format with AM/PM (matching Google Sheets format)
            # Format: "5:00 PM - 6:00 PM" to match Google Sheets
            start_time_str = game.time_slot.start_time.strftime("%I:%M %p").lstrip('0')
            end_time_str = game.time_slot.end_time.strftime("%I:%M %p").lstrip('0')
            time_str = f"{start_time_str} - {end_time_str}"
            
            games_response.append(GameResponse(
                id=game.id,
                home_team=home_team_display,
                away_team=away_team_display,
                date=date_str,
                day=day_str,
                time=time_str,
                facility=facility_display,
                court=game.time_slot.court_number,
                division=game.division.value
            ))
        
        # Calculate generation time
        generation_time = (datetime.now() - start_time).total_seconds()
        
        # Prepare validation summary
        validation_summary = {
            "is_valid": validation_result.is_valid,
            "hard_violations": len(validation_result.hard_constraint_violations),
            "soft_violations": len(validation_result.soft_constraint_violations),
            "total_penalty": validation_result.total_penalty_score
        }
        
        # Build success message
        message = f"Schedule generated successfully with {len(schedule.games)} games"
        
        return ScheduleResponse(
            success=True,
            message=message,
            total_games=len(schedule.games),
            games=games_response,
            validation=validation_summary,
            generation_time=generation_time
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Schedule generation failed: {str(e)}")


@router.get("/stats", response_model=ScheduleStats)
async def get_schedule_stats():
    """
    Get statistics about teams and potential schedule.
    """
    try:
        # Load data from Google Sheets
        reader = SheetsReader()
        teams, facilities, rules = reader.load_all_data()
        
        # Calculate stats
        games_by_division = {}
        for team in teams:
            div_name = team.division.value
            if div_name not in games_by_division:
                games_by_division[div_name] = 0
        
        # Estimate games (8 games per team / 2 since each game has 2 teams)
        for div_name in games_by_division:
            div_teams = [t for t in teams if t.division.value == div_name]
            games_by_division[div_name] = len(div_teams) * 8 // 2
        
        total_estimated_games = sum(games_by_division.values())
        
        return ScheduleStats(
            total_teams=len(teams),
            total_games=total_estimated_games,
            games_by_division=games_by_division,
            teams_with_8_games=0,  # Will be calculated after generation
            teams_under_8_games=0,
            teams_over_8_games=0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/data")
async def get_scheduling_data():
    """
    Get all scheduling data from Google Sheets for display.
    Returns rules, teams, facilities, schools, tiers, and other information.
    """
    try:
        # Load data from Google Sheets
        reader = SheetsReader()
        teams, facilities, rules = reader.load_all_data()
        
        # Extract unique schools
        schools_dict = {}
        for team in teams:
            school_name = team.school.name
            if school_name not in schools_dict:
                schools_dict[school_name] = {
                    "name": school_name,
                    "cluster": team.cluster.value if team.cluster else None,
                    "tier": team.tier.value if team.tier else None,
                    "teams": []
                }
            schools_dict[school_name]["teams"].append({
                "id": team.id,
                "division": team.division.value,
                "coach": team.coach_name,
                "email": team.coach_email
            })
        
        schools = list(schools_dict.values())
        
        # Format teams data
        teams_data = []
        for team in teams:
            teams_data.append({
                "id": team.id,
                "school": team.school.name,
                "division": team.division.value,
                "coach_name": team.coach_name,
                "coach_email": team.coach_email,
                "tier": team.tier.value if team.tier else None,
                "cluster": team.cluster.value if team.cluster else None,
                "home_facility": team.home_facility,
                "rivals_count": len(team.rivals),
                "do_not_play_count": len(team.do_not_play)
            })
        
        # Format facilities data
        facilities_data = []
        for facility in facilities:
            facilities_data.append({
                "name": facility.name,
                "address": facility.address,
                "max_courts": facility.max_courts,
                "has_8ft_rims": facility.has_8ft_rims,
                "available_dates_count": len(facility.available_dates),
                "unavailable_dates_count": len(facility.unavailable_dates),
                "notes": facility.notes
            })
        
        # Format rules data
        rules_data = {
            "season_start": rules.get("season_start"),
            "season_end": rules.get("season_end"),
            "holidays": rules.get("holidays", []),
            "game_duration_minutes": 60,
            "weeknight_time": "5:00 PM - 8:30 PM",
            "saturday_time": "8:00 AM - 6:00 PM",
            "no_games_on_sunday": True,
            "games_per_team": 8,
            "max_games_per_7_days": 2,
            "max_games_per_14_days": 3,
            "max_doubleheaders_per_season": 1,
            "weeknight_slots_required": 3
        }
        
        # Get divisions summary
        divisions_summary = {}
        for team in teams:
            div = team.division.value
            if div not in divisions_summary:
                divisions_summary[div] = {
                    "name": div,
                    "team_count": 0,
                    "estimated_games": 0
                }
            divisions_summary[div]["team_count"] += 1
        
        # Calculate estimated games
        for div in divisions_summary.values():
            div["estimated_games"] = (div["team_count"] * 8) // 2
        
        # Get clusters summary
        clusters_summary = {}
        for team in teams:
            if team.cluster:
                cluster = team.cluster.value
                if cluster not in clusters_summary:
                    clusters_summary[cluster] = {"name": cluster, "team_count": 0, "school_count": 0}
                clusters_summary[cluster]["team_count"] += 1
        
        # Count schools per cluster
        for school in schools:
            if school["cluster"]:
                cluster = school["cluster"]
                if cluster in clusters_summary:
                    clusters_summary[cluster]["school_count"] += 1
        
        # Get tiers summary
        tiers_summary = {}
        for team in teams:
            if team.tier:
                tier = team.tier.value
                if tier not in tiers_summary:
                    tiers_summary[tier] = {"name": tier, "team_count": 0, "school_count": 0}
                tiers_summary[tier]["team_count"] += 1
        
        # Count schools per tier
        for school in schools:
            if school["tier"]:
                tier = school["tier"]
                if tier in tiers_summary:
                    tiers_summary[tier]["school_count"] += 1
        
        return {
            "success": True,
            "rules": rules_data,
            "teams": teams_data,
            "facilities": facilities_data,
            "schools": schools,
            "divisions": list(divisions_summary.values()),
            "clusters": list(clusters_summary.values()),
            "tiers": list(tiers_summary.values()),
            "summary": {
                "total_teams": len(teams),
                "total_facilities": len(facilities),
                "total_schools": len(schools),
                "total_divisions": len(divisions_summary),
                "total_estimated_games": sum(d["estimated_games"] for d in divisions_summary.values())
            }
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load scheduling data: {str(e)}")


@router.get("/info")
async def get_schedule_info():
    """
    Get detailed information about teams, facilities, schools, rankings, and scheduling rules.
    """
    try:
        # Load data from Google Sheets
        reader = SheetsReader()
        teams, facilities, rules = reader.load_all_data()
        
        # Organize teams by division
        teams_by_division: Dict[str, List[Dict]] = {}
        schools_dict: Dict[str, Dict] = {}
        
        for team in teams:
            div_name = team.division.value
            if div_name not in teams_by_division:
                teams_by_division[div_name] = []
            
            # Collect school information
            school_key = team.school.name
            if school_key not in schools_dict:
                schools_dict[school_key] = {
                    "name": team.school.name,
                    "cluster": team.school.cluster.value if team.school.cluster else None,
                    "tier": team.school.tier.value if team.school.tier else None,
                    "teams": []
                }
            
            # Add team to school
            schools_dict[school_key]["teams"].append({
                "id": team.id,
                "division": div_name,
                "coach_name": team.coach_name,
                "coach_email": team.coach_email
            })
            
            # Team information
            team_info = {
                "id": team.id,
                "school_name": team.school.name,
                "division": div_name,
                "coach_name": team.coach_name,
                "coach_email": team.coach_email,
                "home_facility": team.home_facility,
                "tier": team.tier.value if team.tier else None,
                "cluster": team.cluster.value if team.cluster else None,
                "rivals": list(team.rivals),
                "do_not_play": list(team.do_not_play)
            }
            teams_by_division[div_name].append(team_info)
        
        # Facility information
        facilities_info = []
        for facility in facilities:
            facility_info = {
                "name": facility.name,
                "address": facility.address,
                "max_courts": facility.max_courts,
                "has_8ft_rims": facility.has_8ft_rims,
                "notes": facility.notes,
                "available_dates_count": len(facility.available_dates),
                "unavailable_dates_count": len(facility.unavailable_dates),
                "available_dates": [str(d) for d in facility.available_dates[:10]],  # First 10
                "unavailable_dates": [str(d) for d in facility.unavailable_dates[:10]]  # First 10
            }
            facilities_info.append(facility_info)
        
        # Ranking/Tier information and scheduling rules are already imported at the top
        
        scheduling_rules = {
            "season": {
                "start_date": SEASON_START_DATE,
                "end_date": SEASON_END_DATE
            },
            "game_duration": {
                "minutes": GAME_DURATION_MINUTES
            },
            "time_rules": {
                "weeknight": {
                    "start_time": WEEKNIGHT_START_TIME.strftime("%I:%M %p"),
                    "end_time": WEEKNIGHT_END_TIME.strftime("%I:%M %p"),
                    "slots": WEEKNIGHT_SLOTS
                },
                "saturday": {
                    "start_time": SATURDAY_START_TIME.strftime("%I:%M %p"),
                    "end_time": SATURDAY_END_TIME.strftime("%I:%M %p")
                },
                "no_sunday_games": NO_GAMES_ON_SUNDAY
            },
            "frequency_rules": {
                "max_games_per_7_days": MAX_GAMES_PER_7_DAYS,
                "max_games_per_14_days": MAX_GAMES_PER_14_DAYS,
                "max_doubleheaders_per_season": MAX_DOUBLEHEADERS_PER_SEASON,
                "doubleheader_break_minutes": DOUBLEHEADER_BREAK_MINUTES
            },
            "holidays": US_HOLIDAYS,
            "divisions": DIVISIONS,
            "recreational_divisions": REC_DIVISIONS,
            "es_k1_rec_special": {
                "priority_sites": ES_K1_REC_PRIORITY_SITES
            },
            "priority_weights": PRIORITY_WEIGHTS
        }
        
        return {
            "teams": teams_by_division,
            "facilities": facilities_info,
            "schools": list(schools_dict.values()),
            "rankings": {
                "tiers": TIERS,
                "clusters": CLUSTERS,
                "divisions": DIVISIONS
            },
            "scheduling_rules": scheduling_rules,
            "summary": {
                "total_teams": len(teams),
                "total_facilities": len(facilities),
                "total_schools": len(schools_dict),
                "teams_by_division": {div: len(teams_by_division[div]) for div in teams_by_division}
            }
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get info: {str(e)}")


# Information endpoints
class TeamInfo(BaseModel):
    """Team information response."""
    id: str
    school_name: str
    division: str
    coach_name: str
    coach_email: str
    tier: Optional[str]
    cluster: Optional[str]
    home_facility: Optional[str]
    rivals: List[str]
    do_not_play: List[str]


class FacilityInfo(BaseModel):
    """Facility information response."""
    name: str
    address: str
    max_courts: int
    has_8ft_rims: bool
    notes: str
    available_dates: List[str]
    unavailable_dates: List[str]


class SchoolInfo(BaseModel):
    """School information response."""
    name: str
    cluster: Optional[str]
    tier: Optional[str]
    teams: List[str]  # Team IDs


class RulesInfo(BaseModel):
    """Schedule creation rules information."""
    season_start: str
    season_end: str
    game_duration_minutes: int
    weeknight_start_time: str
    weeknight_end_time: str
    saturday_start_time: str
    saturday_end_time: str
    weeknight_slots: int
    max_games_per_7_days: int
    max_games_per_14_days: int
    max_doubleheaders_per_season: int
    doubleheader_break_minutes: int
    no_games_on_sunday: bool
    holidays: List[str]
    divisions: List[str]
    tiers: List[str]
    clusters: List[str]
    priority_weights: Dict[str, int]
    es_k1_rec_rules: Dict[str, Any]


@router.get("/teams", response_model=List[TeamInfo])
async def get_teams_info():
    """Get all team information."""
    try:
        reader = SheetsReader()
        teams = reader.load_teams()
        
        teams_info = []
        for team in teams:
            teams_info.append(TeamInfo(
                id=team.id,
                school_name=team.school.name,
                division=team.division.value,
                coach_name=team.coach_name,
                coach_email=team.coach_email,
                tier=team.tier.value if team.tier else None,
                cluster=team.cluster.value if team.cluster else None,
                home_facility=team.home_facility,
                rivals=list(team.rivals),
                do_not_play=list(team.do_not_play)
            ))
        
        return teams_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get teams info: {str(e)}")


@router.get("/facilities", response_model=List[FacilityInfo])
async def get_facilities_info():
    """Get all facility/stadium information."""
    try:
        reader = SheetsReader()
        facilities = reader.load_facilities()
        
        facilities_info = []
        for facility in facilities:
            facilities_info.append(FacilityInfo(
                name=facility.name,
                address=facility.address,
                max_courts=facility.max_courts,
                has_8ft_rims=facility.has_8ft_rims,
                notes=facility.notes,
                available_dates=[d.isoformat() for d in facility.available_dates],
                unavailable_dates=[d.isoformat() for d in facility.unavailable_dates]
            ))
        
        return facilities_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get facilities info: {str(e)}")


@router.get("/schools", response_model=List[SchoolInfo])
async def get_schools_info():
    """Get all school information."""
    try:
        reader = SheetsReader()
        schools = reader.load_schools()
        teams = reader.load_teams()
        
        # Group teams by school
        school_teams: Dict[str, List[str]] = {}
        for team in teams:
            school_name = team.school.name
            if school_name not in school_teams:
                school_teams[school_name] = []
            school_teams[school_name].append(team.id)
        
        schools_info = []
        for school_name, school in schools.items():
            schools_info.append(SchoolInfo(
                name=school.name,
                cluster=school.cluster.value if school.cluster else None,
                tier=school.tier.value if school.tier else None,
                teams=school_teams.get(school_name, [])
            ))
        
        return schools_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get schools info: {str(e)}")


@router.get("/rules", response_model=RulesInfo)
async def get_rules_info():
    """Get schedule creation rules."""
    try:
        reader = SheetsReader()
        rules = reader.load_rules()
        
        return RulesInfo(
            season_start=SEASON_START_DATE,
            season_end=SEASON_END_DATE,
            game_duration_minutes=GAME_DURATION_MINUTES,
            weeknight_start_time=WEEKNIGHT_START_TIME.strftime("%I:%M %p"),
            weeknight_end_time=WEEKNIGHT_END_TIME.strftime("%I:%M %p"),
            saturday_start_time=SATURDAY_START_TIME.strftime("%I:%M %p"),
            saturday_end_time=SATURDAY_END_TIME.strftime("%I:%M %p"),
            weeknight_slots=WEEKNIGHT_SLOTS,
            max_games_per_7_days=MAX_GAMES_PER_7_DAYS,
            max_games_per_14_days=MAX_GAMES_PER_14_DAYS,
            max_doubleheaders_per_season=MAX_DOUBLEHEADERS_PER_SEASON,
            doubleheader_break_minutes=DOUBLEHEADER_BREAK_MINUTES,
            no_games_on_sunday=NO_GAMES_ON_SUNDAY,
            holidays=US_HOLIDAYS,
            divisions=DIVISIONS,
            tiers=TIERS,
            clusters=CLUSTERS,
            priority_weights=PRIORITY_WEIGHTS,
            es_k1_rec_rules={
                "rim_height": ES_K1_REC_RIM_HEIGHT,
                "officials": ES_K1_REC_OFFICIALS,
                "priority_sites": ES_K1_REC_PRIORITY_SITES
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get rules info: {str(e)}")
