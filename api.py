"""
FastAPI backend for NCSAA Basketball Scheduling System.
Provides REST API endpoints for schedule generation.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from sheets_reader import SheetsReader
from sheets_writer import SheetsWriter
from scheduler import ScheduleOptimizer
from validator import ScheduleValidator
from models import Game, Division

app = FastAPI(
    title="NCSAA Basketball Scheduling API",
    description="API for generating and managing basketball game schedules",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "NCSAA Basketball Scheduling API",
        "version": "1.0.0",
        "endpoints": {
            "generate": "/api/schedule",
            "stats": "/api/stats",
            "health": "/api/health"
        }
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/schedule", response_model=ScheduleResponse)
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
        
        # Generate schedule
        print(f"Generating schedule for {len(teams)} teams...")
        optimizer = ScheduleOptimizer(teams, facilities, rules)
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
        
        # Write schedule to Google Sheets
        sheets_written = False
        sheets_error = None
        try:
            print("Writing schedule to Google Sheets...")
            writer = SheetsWriter()
            writer.write_schedule(schedule)
            writer.write_summary_sheet(schedule, validation_result)
            writer.write_team_schedules(schedule)
            sheets_written = True
            print("Schedule successfully written to Google Sheets!")
        except Exception as e:
            sheets_error = str(e)
            print(f"Warning: Failed to write schedule to Google Sheets: {e}")
            import traceback
            traceback.print_exc()
        
        # Prepare validation summary
        validation_summary = {
            "is_valid": validation_result.is_valid,
            "hard_violations": len(validation_result.hard_constraint_violations),
            "soft_violations": len(validation_result.soft_constraint_violations),
            "total_penalty": validation_result.total_penalty_score
        }
        
        # Build success message
        message = f"Schedule generated successfully with {len(schedule.games)} games"
        if sheets_written:
            message += " and written to Google Sheets"
        elif sheets_error:
            message += f" (Warning: Google Sheets write failed: {sheets_error})"
        
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


@app.get("/api/stats", response_model=ScheduleStats)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
