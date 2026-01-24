"""
Google Sheets writer for the NCSAA Basketball Scheduling System.
Writes generated schedules back to Google Sheets.
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
from typing import List, Dict
from collections import defaultdict

from models import Schedule, Game, Division
from config import SPREADSHEET_ID, CREDENTIALS_FILE, SHEET_WEEK_PREFIX


class SheetsWriter:
    """
    Writes schedule data back to Google Sheets.
    Creates weekly schedule sheets with formatted game information.
    """
    
    def __init__(self):
        """Initialize the Google Sheets client."""
        self.credentials = self._get_credentials()
        self.client = gspread.authorize(self.credentials)
        self.spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
    
    def _get_credentials(self) -> Credentials:
        """Get Google Sheets API credentials."""
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        return Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    
    def write_schedule(self, schedule: Schedule):
        """
        Write the complete schedule to Google Sheets.
        Creates weekly sheets with all game information.
        
        Args:
            schedule: The schedule to write
        """
        print("\n" + "=" * 60)
        print("Writing schedule to Google Sheets...")
        print("=" * 60)
        
        # Group games by week
        games_by_week = self._group_games_by_week(schedule)
        
        # Write each week to a separate sheet
        for week_num, week_games in sorted(games_by_week.items()):
            self._write_week_sheet(week_num, week_games, schedule)
        
        print("=" * 60)
        print("Schedule writing complete!")
        print("=" * 60)
    
    def _group_games_by_week(self, schedule: Schedule) -> Dict[int, List[Game]]:
        """
        Group games by week number.
        
        Args:
            schedule: The schedule containing all games
            
        Returns:
            Dictionary mapping week number to list of games
        """
        games_by_week = defaultdict(list)
        
        if not schedule.season_start:
            # If no season start, group by actual week
            for game in schedule.games:
                # Calculate week number from year start
                week_num = game.time_slot.date.isocalendar()[1]
                games_by_week[week_num].append(game)
        else:
            # Group by weeks from season start
            for game in schedule.games:
                days_from_start = (game.time_slot.date - schedule.season_start).days
                week_num = days_from_start // 7 + 1
                games_by_week[week_num].append(game)
        
        return games_by_week
    
    def _write_week_sheet(self, week_num: int, games: List[Game], schedule: Schedule):
        """
        Write a single week's schedule to a sheet.
        
        Args:
            week_num: The week number
            games: List of games for this week
            schedule: The complete schedule
        """
        sheet_name = f"{SHEET_WEEK_PREFIX} {week_num}"
        
        print(f"Writing {sheet_name}...")
        
        try:
            # Try to get existing sheet or create new one
            try:
                sheet = self.spreadsheet.worksheet(sheet_name)
                # Clear existing content
                sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                # Create new sheet
                sheet = self.spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=100,
                    cols=20
                )
            
            # Prepare data
            data = self._format_week_data(week_num, games, schedule)
            
            # Write data to sheet
            if data:
                sheet.update('A1', data)
                
                # Format header row
                sheet.format('A1:J1', {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8}
                })
            
            print(f"  Wrote {len(games)} games to {sheet_name}")
            
        except Exception as e:
            print(f"  Error writing {sheet_name}: {e}")
    
    def _format_week_data(self, week_num: int, games: List[Game], schedule: Schedule) -> List[List[str]]:
        """
        Format week data for writing to sheet.
        
        Args:
            week_num: The week number
            games: List of games for this week
            schedule: The complete schedule
            
        Returns:
            2D list of formatted data
        """
        # Header row
        data = [[
            'Date',
            'Day',
            'Time',
            'Division',
            'Home Team (Coach)',
            'Away Team (Coach)',
            'Facility',
            'Court',
            'Home School',
            'Away School'
        ]]
        
        # Sort games by date and time
        sorted_games = sorted(games, key=lambda g: (g.time_slot.date, g.time_slot.start_time))
        
        # Add game rows
        for game in sorted_games:
            slot = game.time_slot
            
            # Format date
            date_str = slot.date.strftime('%Y-%m-%d')
            day_str = slot.date.strftime('%A')
            
            # Format time
            time_str = f"{slot.start_time.strftime('%I:%M %p')} - {slot.end_time.strftime('%I:%M %p')}"
            
            # Format team names with coach names
            home_team_display = f"{game.home_team.school.name} ({game.home_team.coach_name})"
            away_team_display = f"{game.away_team.school.name} ({game.away_team.coach_name})"
            
            # Format facility with court
            facility_display = slot.facility.name
            if slot.court_number and slot.court_number > 0:
                facility_display = f"{facility_display} - Court {slot.court_number}"
            
            # Game info
            row = [
                date_str,
                day_str,
                time_str,
                game.division.value,
                home_team_display,
                away_team_display,
                facility_display,
                str(slot.court_number),
                game.home_team.school.name,
                game.away_team.school.name
            ]
            
            data.append(row)
        
        return data
    
    def write_summary_sheet(self, schedule: Schedule, validation_result=None):
        """
        Write a summary sheet with schedule statistics and validation results.
        
        Args:
            schedule: The schedule to summarize
            validation_result: Optional validation results
        """
        sheet_name = "SCHEDULE SUMMARY"
        
        print(f"\nWriting {sheet_name}...")
        
        try:
            # Try to get existing sheet or create new one
            try:
                sheet = self.spreadsheet.worksheet(sheet_name)
                sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                sheet = self.spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=100,
                    cols=10
                )
            
            # Prepare summary data
            data = []
            
            # Title
            data.append(['NCSAA Basketball Schedule Summary'])
            data.append([])
            
            # Basic info
            data.append(['Season Information'])
            data.append(['Season Start:', str(schedule.season_start)])
            data.append(['Season End:', str(schedule.season_end)])
            data.append(['Total Games:', str(len(schedule.games))])
            data.append([])
            
            # Games by division
            data.append(['Games by Division'])
            for division in Division:
                div_games = schedule.get_games_by_division(division)
                if div_games:
                    data.append([division.value, str(len(div_games))])
            data.append([])
            
            # Games by week
            data.append(['Games by Week'])
            games_by_week = self._group_games_by_week(schedule)
            for week_num in sorted(games_by_week.keys()):
                week_games = games_by_week[week_num]
                data.append([f'Week {week_num}', str(len(week_games))])
            data.append([])
            
            # Validation results
            if validation_result:
                data.append(['Validation Results'])
                data.append(['Valid:', 'Yes' if validation_result.is_valid else 'No'])
                data.append(['Hard Violations:', str(len(validation_result.hard_constraint_violations))])
                data.append(['Soft Violations:', str(len(validation_result.soft_constraint_violations))])
                data.append(['Penalty Score:', f'{validation_result.total_penalty_score:.2f}'])
                data.append([])
                
                if validation_result.hard_constraint_violations:
                    data.append(['Hard Constraint Violations:'])
                    for violation in validation_result.hard_constraint_violations[:20]:
                        data.append([violation.constraint_type, violation.description])
                    data.append([])
            
            # Team statistics
            data.append(['Team Statistics'])
            data.append(['Team ID', 'Total Games', 'Home Games', 'Away Games', 'Balance'])
            
            teams = set()
            for game in schedule.games:
                teams.add(game.home_team)
                teams.add(game.away_team)
            
            from validator import ScheduleValidator
            validator = ScheduleValidator()
            
            for team in sorted(teams, key=lambda t: t.id):
                stats = validator.get_team_stats(team, schedule)
                balance = stats.home_games - stats.away_games
                balance_str = f'+{balance}' if balance > 0 else str(balance)
                
                data.append([
                    team.id,
                    str(stats.total_games),
                    str(stats.home_games),
                    str(stats.away_games),
                    balance_str
                ])
            
            # Write data
            if data:
                sheet.update('A1', data)
                
                # Format headers
                sheet.format('A1', {
                    'textFormat': {'bold': True, 'fontSize': 14}
                })
            
            print(f"  Wrote summary to {sheet_name}")
            
        except Exception as e:
            print(f"  Error writing {sheet_name}: {e}")
    
    def write_team_schedules(self, schedule: Schedule):
        """
        Write individual team schedules to a sheet.
        
        Args:
            schedule: The schedule to write
        """
        sheet_name = "TEAM SCHEDULES"
        
        print(f"\nWriting {sheet_name}...")
        
        try:
            # Try to get existing sheet or create new one
            try:
                sheet = self.spreadsheet.worksheet(sheet_name)
                sheet.clear()
            except gspread.exceptions.WorksheetNotFound:
                sheet = self.spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=500,
                    cols=15
                )
            
            # Prepare data
            data = []
            
            # Get all teams
            teams = set()
            for game in schedule.games:
                teams.add(game.home_team)
                teams.add(game.away_team)
            
            # Write each team's schedule
            for team in sorted(teams, key=lambda t: (t.division.value, t.school.name)):
                # Team header
                data.append([])
                data.append([f'{team.school.name} ({team.coach_name}) - {team.division.value}'])
                data.append(['Date', 'Time', 'Opponent', 'Home/Away', 'Facility', 'Court'])
                
                # Get team games
                team_games = sorted(schedule.get_team_games(team), key=lambda g: (g.time_slot.date, g.time_slot.start_time))
                
                for game in team_games:
                    slot = game.time_slot
                    opponent = game.get_opponent(team)
                    home_away = 'Home' if game.is_home_game(team) else 'Away'
                    
                    # Format opponent with coach name
                    opponent_display = f"{opponent.school.name} ({opponent.coach_name})" if opponent else 'Unknown'
                    
                    # Format facility with court
                    facility_display = slot.facility.name
                    if slot.court_number and slot.court_number > 0:
                        facility_display = f"{facility_display} - Court {slot.court_number}"
                    
                    date_str = slot.date.strftime('%Y-%m-%d (%a)')
                    time_str = slot.start_time.strftime('%I:%M %p')
                    
                    data.append([
                        date_str,
                        time_str,
                        opponent_display,
                        home_away,
                        facility_display,
                        str(slot.court_number)
                    ])
            
            # Write data
            if data:
                sheet.update('A1', data)
            
            print(f"  Wrote {len(teams)} team schedules to {sheet_name}")
            
        except Exception as e:
            print(f"  Error writing {sheet_name}: {e}")
