from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from celery.result import AsyncResult

from app.services.sheets_reader import SheetsReader
from app.services.scheduler import ScheduleOptimizer
from app.services.validator import ScheduleValidator
from app.core.config import (
    SEASON_START_DATE, SEASON_END_DATE,
    WEEKNIGHT_START_TIME, WEEKNIGHT_END_TIME,
    SATURDAY_START_TIME, SATURDAY_END_TIME,
    GAME_DURATION_MINUTES, WEEKNIGHT_SLOTS,
    GAMES_PER_TEAM, MAX_GAMES_PER_7_DAYS, MAX_GAMES_PER_14_DAYS,
    MAX_DOUBLEHEADERS_PER_SEASON, DOUBLEHEADER_BREAK_MINUTES,
    NO_GAMES_ON_SUNDAY, US_HOLIDAYS,
    DIVISIONS, REC_DIVISIONS, TIERS, CLUSTERS,
    ES_K1_REC_RIM_HEIGHT, ES_K1_REC_OFFICIALS, ES_K1_REC_PRIORITY_SITES,
    SATURDAY_PRIORITY_FACILITIES, SATURDAY_SECONDARY_FACILITIES,
    SATURDAY_TARGET_FACILITIES, PRIORITY_WEIGHTS
)
from app.core.celery_app import celery_app
from app.tasks.scheduler_tasks import generate_schedule_task

router = APIRouter(prefix="/api", tags=["schedule"])

class ScheduleRequest(BaseModel):
    force_regenerate: bool = False

class GameResponse(BaseModel):
    id: str
    home_team: str
    away_team: str
    date: str
    day: str
    time: str
    facility: str
    court: int
    division: str


class ScheduleResponse(BaseModel):
    success: bool
    message: str
    total_games: int
    games: List[GameResponse]
    validation: Dict
    generation_time: float


class ScheduleStats(BaseModel):
    total_teams: int
    total_games: int
    games_by_division: Dict[str, int]
    teams_with_8_games: int
    teams_under_8_games: int
    teams_over_8_games: int


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.post("/schedule/async")
async def generate_schedule_async(request: ScheduleRequest):
    try:
        task = generate_schedule_task.delay()
        
        print(f"Current Task Info: {task}")
        
        return {
            "task_id": task.id,
            "status": "PENDING",
            "message": "Schedule generation started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start task: {str(e)}")


@router.get("/schedule/status/{task_id}")
async def get_schedule_status(task_id: str):
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

@router.get("/data")
async def get_scheduling_data():
    try:
        reader = SheetsReader()
        teams, facilities, rules = reader.load_all_data()
        
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
        
        facilities_data = []
        for facility in facilities:
            facilities_data.append({
                "name": facility.name,
                "address": facility.address,
                "max_courts": facility.max_courts,
                "has_8ft_rims": facility.has_8ft_rims,
                "owned_by_school": facility.owned_by_school,
                "available_dates_count": len(facility.available_dates),
                "unavailable_dates_count": len(facility.unavailable_dates)
            })
        
        rules_data = {
            "season_start": rules.get("season_start"),
            "season_end": rules.get("season_end"),
            "holidays": rules.get("holidays", []),
            "game_duration_minutes": 60,
            "weeknight_time": "5:00 PM - 8:30 PM",
            "saturday_time": "8:00 AM - 6:00 PM",
            "no_games_on_sunday": True,
            "games_per_team": GAMES_PER_TEAM,
            "max_games_per_7_days": 2,
            "max_games_per_14_days": 3,
            "max_doubleheaders_per_season": 1,
            "weeknight_slots_required": 3
        }
        
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
        
        for div in divisions_summary.values():
            div["estimated_games"] = (div["team_count"] * 8) // 2
        
        clusters_summary = {}
        for team in teams:
            if team.cluster:
                cluster = team.cluster.value
                if cluster not in clusters_summary:
                    clusters_summary[cluster] = {"name": cluster, "team_count": 0, "school_count": 0}
                clusters_summary[cluster]["team_count"] += 1
        
        for school in schools:
            if school["cluster"]:
                cluster = school["cluster"]
                if cluster in clusters_summary:
                    clusters_summary[cluster]["school_count"] += 1
        
        tiers_summary = {}
        for team in teams:
            if team.tier:
                tier = team.tier.value
                if tier not in tiers_summary:
                    tiers_summary[tier] = {"name": tier, "team_count": 0, "school_count": 0}
                tiers_summary[tier]["team_count"] += 1
        
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

class TeamInfo(BaseModel):
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
    name: str
    address: str
    max_courts: int
    has_8ft_rims: bool
    owned_by_school: Optional[str]
    available_dates: List[str]
    unavailable_dates: List[str]


class SchoolInfo(BaseModel):
    name: str
    cluster: Optional[str]
    tier: Optional[str]
    teams: List[str]


class RulesInfo(BaseModel):
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
