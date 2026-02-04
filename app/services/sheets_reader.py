"""
Google Sheets data reader for the NCSAA Basketball Scheduling System.
Handles reading all data from Google Sheets and converting to data models.
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import re

from app.models import (
    Team, School, Facility, Division, Tier, Cluster,
    Schedule
)
from app.core.config import (
    SPREADSHEET_ID, get_google_credentials,
    SHEET_DATES_NOTES, SHEET_TIERS_CLUSTERS, SHEET_TEAM_LIST,
    SHEET_FACILITIES, SHEET_COMPETITIVE_TIERS
)


class SheetsReader:
    """Reads data from Google Sheets and converts to data models."""
    
    def __init__(self):
        """Initialize the Google Sheets client."""
        self.credentials = self._get_credentials()
        self.client = gspread.authorize(self.credentials)
        self.spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
        
        # Cache for loaded data
        self._teams_cache: Optional[List[Team]] = None
        self._facilities_cache: Optional[List[Facility]] = None
        self._schools_cache: Optional[Dict[str, School]] = None
        self._rules_cache: Optional[Dict] = None
    
    def _get_credentials(self) -> Credentials:
        """Get Google Sheets API credentials from environment or file."""
        return get_google_credentials()
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse a date string in various formats."""
        if not date_str or date_str.strip() == '':
            return None
        
        date_str = date_str.strip()
        
        # Try different date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m/%d/%y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        print(f"Warning: Could not parse date: {date_str}")
        return None
    
    def _parse_enum(self, value: str, enum_class):
        """Parse a string value to an enum, handling variations."""
        if not value:
            return None
        
        value = value.strip()
        
        # Try exact match first
        for enum_item in enum_class:
            if enum_item.value == value:
                return enum_item
        
        # Try case-insensitive match
        value_lower = value.lower()
        for enum_item in enum_class:
            if enum_item.value.lower() == value_lower:
                return enum_item
        
        return None
    
    def load_rules(self) -> Dict:
        """Load scheduling rules from the DATES & NOTES sheet."""
        if self._rules_cache:
            return self._rules_cache
        
        print("Loading scheduling rules...")
        
        try:
            sheet = self.spreadsheet.worksheet(SHEET_DATES_NOTES)
            data = sheet.get_all_values()
            
            rules = {
                'season_start': None,
                'season_end': None,
                'holidays': [],
                'no_game_dates': [],
                'notes': []
            }
            
            # Parse the sheet to extract rules from text
            for i, row in enumerate(data):
                if not row or len(row) == 0:
                    continue
                
                # Look for key information in text
                first_col = str(row[0]).strip() if row[0] else ''
                first_col_lower = first_col.lower()
                
                # Extract season dates from rule 1
                if 'regular season dates' in first_col_lower or 'season dates' in first_col_lower:
                    # Example: "1. Regular Season Dates: January 5 - February 28, 2026."
                    import re
                    date_match = re.search(r'January\s+(\d+)\s*-\s*February\s+(\d+),\s*(\d{4})', first_col, re.IGNORECASE)
                    if date_match:
                        start_day = int(date_match.group(1))
                        end_day = int(date_match.group(2))
                        year = int(date_match.group(3))
                        rules['season_start'] = date(year, 1, start_day)
                        rules['season_end'] = date(year, 2, end_day)
                
                # Extract holidays from rule 7
                elif 'holidays' in first_col_lower and 'january' in first_col_lower:
                    # Example: "7. We will not play any games on the following US Holidays: Monday, January 19 & Monday, February 16"
                    import re
                    jan_match = re.search(r'January\s+(\d+)', first_col, re.IGNORECASE)
                    feb_match = re.search(r'February\s+(\d+)', first_col, re.IGNORECASE)
                    if jan_match:
                        rules['holidays'].append(date(2026, 1, int(jan_match.group(1))))
                    if feb_match:
                        rules['holidays'].append(date(2026, 2, int(feb_match.group(1))))
                
                # Collect all notes
                if first_col and len(first_col) > 10:
                    rules['notes'].append(first_col)
            
            # Fallback to config if dates not found
            if not rules['season_start']:
                from app.core.config import SEASON_START_DATE
                rules['season_start'] = self._parse_date(SEASON_START_DATE)
            if not rules['season_end']:
                from app.core.config import SEASON_END_DATE
                rules['season_end'] = self._parse_date(SEASON_END_DATE)
            
            # Add holidays from config
            from app.core.config import US_HOLIDAYS
            for holiday_str in US_HOLIDAYS:
                holiday_date = self._parse_date(holiday_str)
                if holiday_date and holiday_date not in rules['holidays']:
                    rules['holidays'].append(holiday_date)
            
            self._rules_cache = rules
            print(f"Loaded rules: {rules['season_start']} to {rules['season_end']}, {len(rules['holidays'])} holidays")
            return rules
            
        except Exception as e:
            print(f"Error loading rules: {e}")
            import traceback
            traceback.print_exc()
            # Return defaults from config
            from app.core.config import SEASON_START_DATE, SEASON_END_DATE, US_HOLIDAYS
            return {
                'season_start': self._parse_date(SEASON_START_DATE),
                'season_end': self._parse_date(SEASON_END_DATE),
                'holidays': [self._parse_date(h) for h in US_HOLIDAYS if self._parse_date(h)],
                'no_game_dates': [],
                'notes': []
            }
    
    def load_schools(self) -> Dict[str, School]:
        """Load school information and create School objects."""
        if self._schools_cache:
            return self._schools_cache
        
        print("Loading schools...")
        
        schools = {}
        
        try:
            # Load from TIERS, CLUSTERS sheet (for clusters)
            sheet = self.spreadsheet.worksheet(SHEET_TIERS_CLUSTERS)
            data = sheet.get_all_values()
            
            # Find header row
            header_row = 0
            for i, row in enumerate(data):
                if any('school' in str(cell).lower() for cell in row):
                    header_row = i
                    break
            
            headers = [str(h).strip().lower() for h in data[header_row]]
            
            # Find column indices
            school_col = next((i for i, h in enumerate(headers) if 'school' in h), 0)
            cluster_col = next((i for i, h in enumerate(headers) if 'cluster' in h), -1)
            tier_col = next((i for i, h in enumerate(headers) if 'tier' in h), -1)
            
            # Parse school data (clusters and possibly tiers)
            for row in data[header_row + 1:]:
                if not row or len(row) <= school_col:
                    continue
                
                school_name = str(row[school_col]).strip()
                if not school_name or school_name == '':
                    continue
                
                cluster = None
                if cluster_col >= 0 and len(row) > cluster_col:
                    cluster = self._parse_enum(row[cluster_col], Cluster)
                
                tier = None
                if tier_col >= 0 and len(row) > tier_col:
                    tier = self._parse_enum(row[tier_col], Tier)
                
                schools[school_name] = School(
                    name=school_name,
                    cluster=cluster,
                    tier=tier
                )
            
            # CRITICAL: Load tier classifications from COMPETITIVE TIERS sheet
            # This is the authoritative source for tier data
            try:
                tier_sheet = self.spreadsheet.worksheet(SHEET_COMPETITIVE_TIERS)
                tier_data = tier_sheet.get_all_values()
                
                # The sheet has format: Tier 1 | Tier 2 | Tier 3 | Tier 4
                # Row 1: Headers "Tier 1 – Elite..." etc
                # Row 2+: School names in each column
                
                if len(tier_data) > 1:
                    # Map column index to tier
                    tier_map = {
                        1: Tier.TIER_1,  # Column B
                        2: Tier.TIER_2,  # Column C
                        3: Tier.TIER_3,  # Column D
                        4: Tier.TIER_4   # Column E
                    }
                    
                    # Start from row 2 (index 2, after headers)
                    for row in tier_data[2:]:
                        if not row or len(row) < 2:
                            continue
                        
                        # Check each tier column
                        for col_idx, tier in tier_map.items():
                            if len(row) > col_idx:
                                school_name = str(row[col_idx]).strip()
                                if school_name and school_name != '':
                                    # Normalize school name
                                    school_name = self._normalize_school_name(school_name)
                                    
                                    # Update or create school with tier
                                    if school_name in schools:
                                        schools[school_name].tier = tier
                                    else:
                                        schools[school_name] = School(
                                            name=school_name,
                                            cluster=None,
                                            tier=tier
                                        )
                
                print(f"Loaded tier classifications from COMPETITIVE TIERS sheet")
            except Exception as e:
                print(f"Warning: Could not load COMPETITIVE TIERS sheet: {e}")
            
            print(f"Loaded {len(schools)} schools")
            
        except Exception as e:
            print(f"Error loading schools: {e}")
        
        self._schools_cache = schools
        return schools
    
    def _normalize_school_name(self, school_name: str) -> str:
        """
        Normalize school name by removing tier and color suffixes.
        This ensures teams from the same school are grouped together.
        
        Examples:
            'Faith 6A' -> 'Faith'
            'Faith 7A' -> 'Faith'
            'Meadows Blue' -> 'Meadows'
            'Meadows Silver' -> 'Meadows'
            'Somerset Academy NLV' -> 'Somerset Academy NLV'
        """
        if not school_name:
            return school_name
        
        import re
        
        # Remove tier suffixes: 6A, 7A, 8A, etc. (at the end of the name)
        normalized = re.sub(r'\s+\d+[A-Z]\s*$', '', school_name).strip()
        
        # Remove color suffixes: Blue, Silver, White, Black, Gold, Navy, etc.
        # These are team identifiers, not separate schools
        color_suffixes = [
            'Blue', 'Silver', 'White', 'Black', 'Gold', 'Navy', 
            'Red', 'Green', 'Purple', 'Orange', 'Yellow'
        ]
        
        for color in color_suffixes:
            # Remove color at the end of the name (case-insensitive)
            pattern = r'\s+' + re.escape(color) + r'\s*$'
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE).strip()
        
        return normalized
    
    def _parse_team_name(self, team_str: str) -> tuple:
        """
        Parse team name in format "School Name (Coach Last Name)".
        Returns (school_name, coach_last_name).
        """
        if not team_str or not team_str.strip():
            return None, None
        
        team_str = team_str.strip()
        
        # Match pattern: "School Name (Coach Last Name)"
        import re
        match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', team_str)
        if match:
            school_name = match.group(1).strip()
            # Normalize school name to remove tier suffixes
            school_name = self._normalize_school_name(school_name)
            coach_name = match.group(2).strip()
            return school_name, coach_name
        
        # If no parentheses, assume it's just school name
        return self._normalize_school_name(team_str), None
    
    def load_teams(self) -> List[Team]:
        """Load team information from the TEAM LIST sheet."""
        if self._teams_cache:
            return self._teams_cache
        
        print("Loading teams...")
        
        schools = self.load_schools()
        teams = []
        
        try:
            sheet = self.spreadsheet.worksheet(SHEET_TEAM_LIST)
            data = sheet.get_all_values()
            
            # Find header row (should be row 1, index 0)
            header_row = 0
            headers = data[header_row] if data else []
            
            # Teams are organized by division in columns
            # Headers: ['#', 'ES K-1 REC', 'ES 2-3 REC', "ES BOY'S COMP", ...]
            division_columns = {}
            
            # Map division names from headers to Division enum
            division_mapping = {
                'ES K-1 REC': Division.ES_K1_REC,
                'ES 2-3 REC': Division.ES_23_REC,
                "ES BOY'S COMP": Division.ES_BOYS_COMP,
                "ES GIRL'S COMP": Division.ES_GIRLS_COMP,
                " BOY'S JV": Division.BOYS_JV,
                " GIRL'S JV": Division.GIRLS_JV,
            }
            
            # Find division columns
            for col_idx, header in enumerate(headers):
                header_clean = header.strip()
                for div_name, div_enum in division_mapping.items():
                    if div_name in header_clean or header_clean in div_name:
                        division_columns[col_idx] = div_enum
                        break
            
            print(f"Found {len(division_columns)} division columns: {division_columns}")
            
            # Parse teams from each division column
            # Skip header row (0) and count row (1)
            for row_idx, row in enumerate(data[2:], start=2):
                if not row:
                    continue
                
                # Process each division column
                for col_idx, division in division_columns.items():
                    if col_idx >= len(row):
                        continue
                    
                    team_str = str(row[col_idx]).strip()
                    if not team_str or team_str == '' or team_str.lower() == 'none':
                        continue
                    
                    # Parse team name "School Name (Coach Last Name)"
                    school_name, coach_last_name = self._parse_team_name(team_str)
                    if not school_name:
                        continue
                    
                    # Get or create school
                    if school_name not in schools:
                        schools[school_name] = School(name=school_name)
                    school = schools[school_name]
                    
                    # Generate unique team ID
                    team_id = f"{school_name}_{division.value}"
                    if coach_last_name:
                        team_id += f"_{coach_last_name}"
                    # Add row number to ensure uniqueness
                    team_id += f"_R{row_idx}"
                    team_id = team_id.replace(' ', '_').replace('/', '_').replace('-', '_')
                    
                    # Check for duplicate teams
                    existing_team_ids = {t.id for t in teams}
                    if team_id in existing_team_ids:
                        # Make it unique by adding counter
                        counter = 1
                        original_id = team_id
                        while team_id in existing_team_ids:
                            team_id = f"{original_id}_{counter}"
                            counter += 1
                    
                    # Get home facility from school name (if school hosts)
                    home_facility = None
                    # This will be set based on facilities sheet later
                    
                    team = Team(
                        id=team_id,
                        school=school,
                        division=division,
                        coach_name=coach_last_name or '',
                        coach_email='',  # Not in this format
                        home_facility=home_facility,
                        tier=school.tier,
                        cluster=school.cluster
                    )
                    
                    teams.append(team)
            
            print(f"Loaded {len(teams)} teams")
            
        except Exception as e:
            print(f"Error loading teams: {e}")
            import traceback
            traceback.print_exc()
        
        self._teams_cache = teams
        return teams
    
    def _parse_date_range(self, date_str: str) -> List[date]:
        """
        Parse date string like "Jan. 6, 7, 8, 15, 22, 29  Feb. 5, 12, 19, 26"
        Returns list of dates.
        """
        if not date_str or not date_str.strip():
            return []
        
        dates = []
        import re
        
        # Match month and days: "Jan. 6, 7, 8" or "January 6, 7"
        pattern = r'(Jan|Jan\.|January|Feb|Feb\.|February)\s+([\d,\s-]+)'
        matches = re.findall(pattern, date_str, re.IGNORECASE)
        
        for month_str, days_str in matches:
            # Normalize month
            month_num = 1 if 'jan' in month_str.lower() else 2
            
            # Parse days (handle ranges like "17-19" and lists like "6, 7, 8")
            day_pattern = r'(\d+)(?:-(\d+))?'
            day_matches = re.findall(day_pattern, days_str)
            
            for day_match in day_matches:
                start_day = int(day_match[0])
                end_day = int(day_match[1]) if day_match[1] else start_day
                
                for day in range(start_day, end_day + 1):
                    try:
                        dates.append(date(2026, month_num, day))
                    except ValueError:
                        continue  # Invalid date (e.g., Feb 30)
        
        return dates
    
    def load_facilities(self) -> List[Facility]:
        """Load facility information from the FACILITIES sheet."""
        if self._facilities_cache:
            return self._facilities_cache
        
        print("Loading facilities...")
        
        facilities_dict = {}  # Group by facility name
        
        try:
            sheet = self.spreadsheet.worksheet(SHEET_FACILITIES)
            data = sheet.get_all_values()
            
            # Header row is row 1 (index 0)
            header_row = 0
            headers = [str(h).strip().upper() for h in data[header_row]]
            
            # Find column indices
            # Headers: ['SITE', 'DATES', 'COURT', 'START TIME', 'END TIME', 'GAME LENGTH', 'DIVISIONS ALLOWED', 'NOTES']
            site_col = next((i for i, h in enumerate(headers) if 'SITE' in h), 0)
            dates_col = next((i for i, h in enumerate(headers) if 'DATES' in h), 1)
            court_col = next((i for i, h in enumerate(headers) if 'COURT' in h), 2)
            start_time_col = next((i for i, h in enumerate(headers) if 'START TIME' in h), 3)
            end_time_col = next((i for i, h in enumerate(headers) if 'END TIME' in h), 4)
            notes_col = next((i for i, h in enumerate(headers) if 'NOTE' in h), 7)
            
            # Parse facility data
            for row in data[header_row + 1:]:
                if not row or len(row) <= site_col:
                    continue
                
                facility_name = str(row[site_col]).strip()
                if not facility_name or facility_name == '':
                    continue
                
                # Parse dates
                dates_str = str(row[dates_col]).strip() if len(row) > dates_col else ''
                available_dates = self._parse_date_range(dates_str)
                
                # DEBUG: Log date parsing for key facilities
                if facility_name and ('faith' in facility_name.lower() or 'lvbc' in facility_name.lower() or 'las vegas basketball' in facility_name.lower()):
                    if dates_str:
                        print(f"  [FACILITY] {facility_name} - {court_name}: dates_str='{dates_str[:100]}...' → parsed {len(available_dates)} dates")
                        if available_dates:
                            print(f"    First 5 dates: {sorted(available_dates)[:5]}")
                    else:
                        print(f"  [FACILITY] {facility_name} - {court_name}: NO dates string (empty DATES column)")
                
                # Parse court name
                court_name = str(row[court_col]).strip() if len(row) > court_col else ''
                
                # Create unique facility name with court
                full_facility_name = f"{facility_name} - {court_name}" if court_name else facility_name
                
                # Check if facility already exists
                if full_facility_name not in facilities_dict:
                    # Determine if has 8ft rims (check notes and court name)
                    notes = str(row[notes_col]).strip() if len(row) > notes_col else ''
                    has_8ft_rims = '8 foot' in notes.lower() or '8ft' in notes.lower() or 'K-1' in court_name.upper()
                    
                    # Count courts (estimate from court name)
                    max_courts = 1
                    if 'court' in court_name.lower():
                        # Try to extract court numbers
                        import re
                        court_numbers = re.findall(r'\d+', court_name)
                        if court_numbers:
                            max_courts = len(court_numbers)
                        elif 'court' in court_name.lower() and 'courts' in court_name.lower():
                            max_courts = 2
                    
                    facility = Facility(
                        name=full_facility_name,
                        address=facility_name,  # Use facility name as address
                        max_courts=max_courts,
                        has_8ft_rims=has_8ft_rims,
                        notes=notes
                    )
                    
                    facilities_dict[full_facility_name] = facility
                else:
                    facility = facilities_dict[full_facility_name]
                
                # Add dates to facility availability
                facility.available_dates.extend(available_dates)
                facility.available_dates = list(set(facility.available_dates))  # Remove duplicates
            
            facilities = list(facilities_dict.values())
            
            print(f"Loaded {len(facilities)} facilities")
            
            # Summary: Show facilities with and without date restrictions
            facilities_with_dates = [f for f in facilities if f.available_dates]
            facilities_without_dates = [f for f in facilities if not f.available_dates]
            
            print(f"  Facilities with specific dates: {len(facilities_with_dates)}")
            print(f"  Facilities available all season: {len(facilities_without_dates)}")
            
        except Exception as e:
            print(f"Error loading facilities: {e}")
            import traceback
            traceback.print_exc()
        
        self._facilities_cache = facilities
        return facilities
    
    def load_rivals_and_restrictions(self, teams: List[Team]) -> None:
        """Load rival and do-not-play relationships from the sheet."""
        print("Loading rival and restriction data...")
        
        try:
            sheet = self.spreadsheet.worksheet(SHEET_TIERS_CLUSTERS)
            data = sheet.get_all_values()
            
            # Create team lookup by school name and division
            team_lookup = {}
            for team in teams:
                key = f"{team.school.name}_{team.division.value}"
                team_lookup[key] = team
            
            # Find relevant columns
            header_row = 0
            for i, row in enumerate(data):
                if any('rival' in str(cell).lower() or 'do not play' in str(cell).lower() for cell in row):
                    header_row = i
                    break
            
            headers = [str(h).strip().lower() for h in data[header_row]]
            
            school_col = next((i for i, h in enumerate(headers) if 'school' in h), 0)
            rivals_col = next((i for i, h in enumerate(headers) if 'rival' in h), -1)
            dnp_col = next((i for i, h in enumerate(headers) if 'do not play' in h), -1)
            
            # Parse relationships
            for row in data[header_row + 1:]:
                if not row or len(row) <= school_col:
                    continue
                
                school_name = str(row[school_col]).strip()
                if not school_name:
                    continue
                
                # Process rivals
                if rivals_col >= 0 and len(row) > rivals_col and row[rivals_col]:
                    rival_schools = [s.strip() for s in str(row[rivals_col]).split(',')]
                    for team in teams:
                        if team.school.name == school_name:
                            for rival_school in rival_schools:
                                for rival_team in teams:
                                    if rival_team.school.name == rival_school and rival_team.division == team.division:
                                        team.rivals.add(rival_team.id)
                
                # Process do-not-play
                if dnp_col >= 0 and len(row) > dnp_col and row[dnp_col]:
                    dnp_schools = [s.strip() for s in str(row[dnp_col]).split(',')]
                    for team in teams:
                        if team.school.name == school_name:
                            for dnp_school in dnp_schools:
                                for dnp_team in teams:
                                    if dnp_team.school.name == dnp_school and dnp_team.division == team.division:
                                        team.do_not_play.add(dnp_team.id)
            
            print(f"Loaded rival and restriction relationships")
            
        except Exception as e:
            print(f"Error loading rivals/restrictions: {e}")
    
    def load_blackouts(self) -> Dict[str, List[date]]:
        """
        Load school blackout dates from Google Sheets.
        
        Returns:
            Dict mapping school name to list of blackout dates
        """
        try:
            from app.core.config import SHEET_BLACKOUTS
            blackouts_sheet = self.spreadsheet.worksheet(SHEET_BLACKOUTS)
            data = blackouts_sheet.get_all_values()
            
            blackouts = {}
            
            for row in data[1:]:  # Skip header row
                if len(row) < 2:
                    continue
                
                school_name = str(row[0]).strip()
                blackout_str = str(row[1]).strip()
                
                if not school_name or not blackout_str:
                    continue
                
                # Normalize school name to match team data
                normalized_name = self._normalize_school_name(school_name)
                
                # Parse dates from blackout string
                # Format: "Blackouts: Jan. 6, 14, 21, 24, 28 Feb. 3, 10, 17, 23, 27"
                dates = self._parse_date_range(blackout_str)
                
                if dates:
                    if normalized_name in blackouts:
                        blackouts[normalized_name].extend(dates)
                    else:
                        blackouts[normalized_name] = dates
            
            print(f"Loaded blackout dates for {len(blackouts)} schools")
            return blackouts
            
        except Exception as e:
            print(f"Warning: Could not load blackouts: {e}")
            return {}
    
    def load_all_data(self) -> Tuple[List[Team], List[Facility], Dict]:
        """Load all data from Google Sheets."""
        print("=" * 60)
        print("Loading all data from Google Sheets...")
        print("=" * 60)
        
        rules = self.load_rules()
        schools = self.load_schools()
        teams = self.load_teams()
        facilities = self.load_facilities()
        blackouts = self.load_blackouts()
        self.load_rivals_and_restrictions(teams)
        
        # Add blackouts to rules
        rules['blackouts'] = blackouts
        
        print("=" * 60)
        print(f"Data loading complete:")
        print(f"  - {len(schools)} schools")
        print(f"  - {len(teams)} teams")
        print(f"  - {len(facilities)} facilities")
        print("=" * 60)
        
        return teams, facilities, rules
