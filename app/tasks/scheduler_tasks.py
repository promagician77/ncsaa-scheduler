"""
Celery tasks for schedule generation.
"""

from app.core.celery_app import celery_app
from app.services.sheets_reader import SheetsReader
from app.services.scheduler_v2 import SchoolBasedScheduler
from app.services.validator import ScheduleValidator
from datetime import datetime
import traceback


@celery_app.task(bind=True, name="generate_schedule")
def generate_schedule_task(self):
    """
    Async task to generate basketball schedule.
    
    Returns:
        dict: Schedule data with games and validation results
    """
    try:
        # Update task state to PROGRESS
        self.update_state(
            state="PROGRESS",
            meta={"status": "Loading data from Google Sheets..."}
        )
        
        start_time = datetime.now()
        
        # Load data from Google Sheets
        reader = SheetsReader()
        teams, facilities, rules = reader.load_all_data()
        
        # Update progress
        self.update_state(
            state="PROGRESS",
            meta={"status": f"Generating schedule for {len(teams)} teams..."}
        )
        
        # Generate schedule using school-based algorithm
        optimizer = SchoolBasedScheduler(teams, facilities, rules)
        schedule = optimizer.optimize_schedule()
        
        # Update progress
        self.update_state(
            state="PROGRESS",
            meta={"status": "Validating schedule..."}
        )
        
        # Validate schedule
        validator = ScheduleValidator()
        validation_result = validator.validate_schedule(schedule)
        
        # Convert games to response format
        games_response = []
        for game in schedule.games:
            # Format team names with coach names
            home_team_display = f"{game.home_team.school.name} ({game.home_team.coach_name})"
            away_team_display = f"{game.away_team.school.name} ({game.away_team.coach_name})"
            
            # Format facility
            facility_display = game.time_slot.facility.name
            if game.time_slot.court_number and game.time_slot.court_number > 0:
                facility_display = f"{facility_display} - Court {game.time_slot.court_number}"
            
            # Format date and time
            date_str = game.time_slot.date.strftime("%Y-%m-%d")
            day_str = game.time_slot.date.strftime("%A")
            start_time_str = game.time_slot.start_time.strftime("%I:%M %p").lstrip('0')
            end_time_str = game.time_slot.end_time.strftime("%I:%M %p").lstrip('0')
            time_str = f"{start_time_str} - {end_time_str}"
            
            games_response.append({
                "id": game.id,
                "home_team": home_team_display,
                "away_team": away_team_display,
                "date": date_str,
                "day": day_str,
                "time": time_str,
                "facility": facility_display,
                "court": game.time_slot.court_number,
                "division": game.division.value
            })
        
        # Calculate generation time
        generation_time = (datetime.now() - start_time).total_seconds()
        
        # Prepare validation summary
        validation_summary = {
            "is_valid": validation_result.is_valid,
            "hard_violations": len(validation_result.hard_constraint_violations),
            "soft_violations": len(validation_result.soft_constraint_violations),
            "total_penalty": validation_result.total_penalty_score
        }
        
        # Return success result
        return {
            "success": True,
            "message": f"Schedule generated successfully with {len(schedule.games)} games",
            "total_games": len(schedule.games),
            "games": games_response,
            "validation": validation_summary,
            "generation_time": generation_time
        }
        
    except Exception as e:
        # Return error result
        error_trace = traceback.format_exc()
        print(f"Error in generate_schedule_task: {error_trace}")
        
        return {
            "success": False,
            "message": f"Schedule generation failed: {str(e)}",
            "error": str(e),
            "traceback": error_trace
        }
