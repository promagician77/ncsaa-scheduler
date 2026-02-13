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
    def __init__(self):
        self.credentials = self._get_credentials()
        self.client = gspread.authorize(self.credentials)
        self.spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
        
        self._teams_cache: Optional[List[Team]] = None
        self._facilities_cache: Optional[List[Facility]] = None
        self._schools_cache: Optional[Dict[str, School]] = None
        self._rules_cache: Optional[Dict] = None
    
    def _get_credentials(self) -> Credentials:
        return get_google_credentials()
    
    def _parse_date(self, date_str: str) -> Optional[date]: 
        if not date_str or date_str.strip() == '':
            return None
        
        date_str = date_str.strip()
        
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
        if not value:
            return None
        
        value = value.strip()
        
        for enum_item in enum_class:
            if enum_item.value == value:
                return enum_item
        
        value_lower = value.lower()
        for enum_item in enum_class:
            if enum_item.value.lower() == value_lower:
                return enum_item
        
        return None
    
    def load_rules(self) -> Dict:
        if self._rules_cache:
            return self._rules_cache
        
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
            
            for i, row in enumerate(data):
                if not row or len(row) == 0:
                    continue
                
                first_col = str(row[0]).strip() if row[0] else ''
                first_col_lower = first_col.lower()
                
                if 'regular season dates' in first_col_lower or 'season dates' in first_col_lower:
                    import re
                    date_match = re.search(r'January\s+(\d+)\s*-\s*February\s+(\d+),\s*(\d{4})', first_col, re.IGNORECASE)
                    if date_match:
                        start_day = int(date_match.group(1))
                        end_day = int(date_match.group(2))
                        year = int(date_match.group(3))
                        rules['season_start'] = date(year, 1, start_day)
                        rules['season_end'] = date(year, 2, end_day)
                
                elif 'holidays' in first_col_lower and 'january' in first_col_lower:
                    import re
                    jan_match = re.search(r'January\s+(\d+)', first_col, re.IGNORECASE)
                    feb_match = re.search(r'February\s+(\d+)', first_col, re.IGNORECASE)
                    if jan_match:
                        rules['holidays'].append(date(2026, 1, int(jan_match.group(1))))
                    if feb_match:
                        rules['holidays'].append(date(2026, 2, int(feb_match.group(1))))
                
                if first_col and len(first_col) > 10:
                    rules['notes'].append(first_col)
            
            if not rules['season_start']:
                from app.core.config import SEASON_START_DATE
                rules['season_start'] = self._parse_date(SEASON_START_DATE)
            if not rules['season_end']:
                from app.core.config import SEASON_END_DATE
                rules['season_end'] = self._parse_date(SEASON_END_DATE)
            
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
            from app.core.config import SEASON_START_DATE, SEASON_END_DATE, US_HOLIDAYS
            return {
                'season_start': self._parse_date(SEASON_START_DATE),
                'season_end': self._parse_date(SEASON_END_DATE),
                'holidays': [self._parse_date(h) for h in US_HOLIDAYS if self._parse_date(h)],
                'no_game_dates': [],
                'notes': []
            }
    
    def load_schools(self) -> Dict[str, School]:
        if self._schools_cache:
            return self._schools_cache
        
        schools = {}
        
        try:
            sheet = self.spreadsheet.worksheet(SHEET_TIERS_CLUSTERS)
            data = sheet.get_all_values()
            
            header_row = 0
            
            headers = [str(h).strip().lower() for h in data[header_row]]
            
            # Debug: print all headers
            print(f"DEBUG: Header row index: {header_row}")
            print(f"DEBUG: Headers found: {headers[:10]}")  # Show first 10 columns
            
            school_col = 0
            tier_col = next((i for i, h in enumerate(headers) if 'tier' in h), -1)
            cluster_col = next((i for i, h in enumerate(headers) if 'cluster' in h), -1)
            rivals_col = next((i for i, h in enumerate(headers) if 'rival' in h), -1)
            dnp_col = next((i for i, h in enumerate(headers) if 'do not play' in h or 'do not' in h), -1)
            blackout_col = next((i for i, h in enumerate(headers) if 'blackouts' in h), -1)
            
            print(f"Found columns: school={school_col}, tier={tier_col}, cluster={cluster_col}, rivals={rivals_col}, dnp={dnp_col}, blackout={blackout_col}")
            
            # Parse each school row
            for row in data[header_row + 1:]:
                if not row or len(row) <= school_col:
                    continue
                
                school_name = str(row[school_col]).strip()
                if not school_name or school_name == '':
                    continue
                
                # Parse tier
                tier = None
                if tier_col >= 0 and len(row) > tier_col:
                    tier = self._parse_enum(row[tier_col], Tier)
                
                # Parse cluster
                cluster = None
                if cluster_col >= 0 and len(row) > cluster_col:
                    cluster = self._parse_enum(row[cluster_col], Cluster)
                
                # Parse rival schools
                rival_schools = set()
                if rivals_col >= 0 and len(row) > rivals_col:
                    rivals_str = str(row[rivals_col]).strip()
                    if rivals_str and rivals_str not in ['—', '--', '']:
                        # Split by semicolon
                        for rival in rivals_str.split(';'):
                            rival = rival.strip()
                            if rival:
                                rival_schools.add(rival)
                
                # Parse do-not-play schools
                do_not_play_schools = set()
                if dnp_col >= 0 and len(row) > dnp_col:
                    dnp_str = str(row[dnp_col]).strip()
                    if dnp_str and dnp_str not in ['—', '--', '']:
                        # Split by semicolon
                        for dnp in dnp_str.split(';'):
                            dnp = dnp.strip()
                            if dnp:
                                do_not_play_schools.add(dnp)
                
                # Parse blackout dates
                blackout_dates = []
                if blackout_col >= 0 and len(row) > blackout_col:
                    blackout_str = str(row[blackout_col]).strip()
                    if blackout_str and blackout_str not in ['—', '--', '']:
                        # Parse date range (e.g., "Jan 10-15")
                        blackout_dates = self._parse_date_range(blackout_str)
                
                # Create school object
                schools[school_name] = School(
                    name=school_name,
                    cluster=cluster,
                    tier=tier,
                    blackout_dates=blackout_dates,
                    rival_schools=rival_schools,
                    do_not_play_schools=do_not_play_schools
                )
            
            print(f"Loaded {len(schools)} schools from TIERS_CLUSTERS sheet")
            print(f"  - {len([s for s in schools.values() if s.rival_schools])} schools with rivals")
            print(f"  - {len([s for s in schools.values() if s.do_not_play_schools])} schools with do-not-play restrictions")
            print(f"  - {len([s for s in schools.values() if s.blackout_dates])} schools with blackout dates")
            
        except Exception as e:
            print(f"Error loading schools: {e}")
            import traceback
            traceback.print_exc()
        
        self._schools_cache = schools
        return schools
    
    def _normalize_school_name(self, school_name: str) -> str:
        """Normalize school names by removing team identifiers and color suffixes."""
        if not school_name:
            return school_name
        
        import re
        
        # Remove trailing team identifiers like "1A", "2B", "3C"
        normalized = re.sub(r'\s+\d+[A-Z]\s*$', '', school_name).strip()
        
        # Remove color suffixes
        color_suffixes = [
            'Blue', 'Silver', 'White', 'Black', 'Gold', 'Navy', 
            'Red', 'Green', 'Purple', 'Orange', 'Yellow'
        ]
        
        for color in color_suffixes:
            pattern = r'\s+' + re.escape(color) + r'\s*$'
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE).strip()
        
        return normalized
    
    def _parse_team_name(self, team_str: str) -> tuple:
        if not team_str or not team_str.strip():
            return None, None
        
        team_str = team_str.strip()
        
        import re
        match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', team_str)
        if match:
            school_name = match.group(1).strip()
            coach_name = match.group(2).strip()
            # Normalize the school name to remove color suffixes and team numbers
            school_name = self._normalize_school_name(school_name)
            return school_name, coach_name
        
        return self._normalize_school_name(team_str), None
    
    def load_teams(self) -> List[Team]:
        if self._teams_cache:
            return self._teams_cache

        schools = self.load_schools()
        teams = []
        
        try:
            sheet = self.spreadsheet.worksheet(SHEET_TEAM_LIST)
            data = sheet.get_all_values()
            
            header_row = 0
            headers = data[header_row] if data else []
            
            division_columns = {}
            
            division_mapping = {
                'ES K-1 REC': Division.ES_K1_REC,
                'ES 2-3 REC': Division.ES_23_REC,
                "ES BOY'S COMP": Division.ES_BOYS_COMP,
                "ES GIRL'S COMP": Division.ES_GIRLS_COMP,
                " BOY'S JV": Division.BOYS_JV,
                " GIRL'S JV": Division.GIRLS_JV,
                "BOY'S VARSITY": Division.BOYS_VARSITY,
                "GIRL'S VARSITY": Division.GIRLS_VARSITY,
            }
            
            for col_idx, header in enumerate(headers):
                header_clean = header.strip()
                for div_name, div_enum in division_mapping.items():
                    if div_name in header_clean or header_clean in div_name:
                        division_columns[col_idx] = div_enum
                        break
            
            print(f"Found {len(division_columns)} division columns: {division_columns}")
            
            for row_idx, row in enumerate(data[2:], start=2):
                if not row:
                    continue
                
                for col_idx, division in division_columns.items():
                    if col_idx >= len(row):
                        continue
                    
                    team_str = str(row[col_idx]).strip()
                    if not team_str or team_str == '' or team_str.lower() == 'none':
                        continue
                    
                    school_name, coach_last_name = self._parse_team_name(team_str)
                    if not school_name:
                        continue
                    
                    if school_name not in schools:
                        schools[school_name] = School(name=school_name)
                    school = schools[school_name]
                    
                    team_id = f"{school_name}_{division.value}"
                    if coach_last_name:
                        team_id += f"_{coach_last_name}"
                    team_id += f"_R{row_idx}"
                    team_id = team_id.replace(' ', '_').replace('/', '_').replace('-', '_')
                    
                    existing_team_ids = {t.id for t in teams}
                    if team_id in existing_team_ids:
                        counter = 1
                        original_id = team_id
                        while team_id in existing_team_ids:
                            team_id = f"{original_id}_{counter}"
                            counter += 1
                    
                    home_facility = None
                    
                    team = Team(
                        id=team_id,
                        school=school,
                        division=division,
                        coach_name=coach_last_name or '',
                        coach_email='',
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
        if not date_str or not date_str.strip():
            return []
        
        dates = []
        import re
        
        pattern = r'(Jan|Jan\.|January|Feb|Feb\.|February)\s+([\d,\s-]+)'
        matches = re.findall(pattern, date_str, re.IGNORECASE)
        
        for month_str, days_str in matches:
            month_num = 1 if 'jan' in month_str.lower() else 2
            
            day_pattern = r'(\d+)(?:-(\d+))?'
            day_matches = re.findall(day_pattern, days_str)
            
            for day_match in day_matches:
                start_day = int(day_match[0])
                end_day = int(day_match[1]) if day_match[1] else start_day
                
                for day in range(start_day, end_day + 1):
                    try:
                        dates.append(date(2026, month_num, day))
                    except ValueError:
                        continue
        
        return dates
    
    def load_facilities(self) -> List[Facility]:
        if self._facilities_cache:
            return self._facilities_cache
        
        facilities_dict = {}
        
        try:
            sheet = self.spreadsheet.worksheet(SHEET_FACILITIES)
            data = sheet.get_all_values()
            
            header_row = 0
            headers = [str(h).strip().upper() for h in data[header_row]]
            
            site_col = next((i for i, h in enumerate(headers) if 'SITE' in h), 0)
            dates_col = next((i for i, h in enumerate(headers) if 'DATES' in h), 1)
            court_col = next((i for i, h in enumerate(headers) if 'COURT' in h), 2)
            start_time_col = next((i for i, h in enumerate(headers) if 'START TIME' in h), 3)
            end_time_col = next((i for i, h in enumerate(headers) if 'END TIME' in h), 4)
            notes_col = next((i for i, h in enumerate(headers) if 'NOTE' in h), 7)
            
            for row in data[header_row + 1:]:
                if not row or len(row) <= site_col:
                    continue
                
                facility_name = str(row[site_col]).strip()
                if not facility_name or facility_name == '':
                    continue
                
                dates_str = str(row[dates_col]).strip() if len(row) > dates_col else ''
                available_dates = self._parse_date_range(dates_str)
                
                if facility_name and ('faith' in facility_name.lower() or 'lvbc' in facility_name.lower() or 'las vegas basketball' in facility_name.lower()):
                    if dates_str:
                        print(f"  [FACILITY] {facility_name} - {court_name}: dates_str='{dates_str[:100]}...' → parsed {len(available_dates)} dates")
                        if available_dates:
                            print(f"    First 5 dates: {sorted(available_dates)[:5]}")
                    else:
                        print(f"  [FACILITY] {facility_name} - {court_name}: NO dates string (empty DATES column)")
                
                court_name = str(row[court_col]).strip() if len(row) > court_col else ''
                
                full_facility_name = f"{facility_name} - {court_name}" if court_name else facility_name
                
                if full_facility_name not in facilities_dict:
                    notes = str(row[notes_col]).strip() if len(row) > notes_col else ''
                    
                    # Extract school name from notes by removing "home court" suffix
                    owned_by_school = None
                    if notes:
                        # Remove "home court" and everything after it (case insensitive)
                        # This handles cases like "School Name home court" or "School Home Court but other text"
                        import re
                        match = re.search(r'^(.*?)\s*home\s*court', notes, flags=re.IGNORECASE)
                        if match:
                            owned_by_school = match.group(1).strip()
                        else:
                            # If no "home court" found, keep the full notes value
                            owned_by_school = notes
                        
                        if owned_by_school == '':
                            owned_by_school = None
                    
                    has_8ft_rims = '8 foot' in notes.lower() or '8ft' in notes.lower() or 'K-1' in court_name.upper()
                    
                    max_courts = 1
                    if 'court' in court_name.lower():
                        court_numbers = re.findall(r'\d+', court_name)
                        if court_numbers:
                            max_courts = len(court_numbers)
                        elif 'court' in court_name.lower() and 'courts' in court_name.lower():
                            max_courts = 2
                    
                    facility = Facility(
                        name=full_facility_name,
                        address=facility_name,
                        max_courts=max_courts,
                        has_8ft_rims=has_8ft_rims,
                        owned_by_school=owned_by_school
                    )
                    
                    facilities_dict[full_facility_name] = facility
                else:
                    facility = facilities_dict[full_facility_name]
                
                facility.available_dates.extend(available_dates)
                facility.available_dates = list(set(facility.available_dates))
            
            facilities = list(facilities_dict.values())
            
            print(f"Loaded {len(facilities)} facilities")
            
            facilities_with_dates = [f for f in facilities if f.available_dates]
            facilities_without_dates = [f for f in facilities if not f.available_dates]
            
            print(f"  Facilities with specific dates: {len(facilities_with_dates)}")
            print(f"  Facilities available all season: {len(facilities_without_dates)}")
            
            # Print facilities with ownership information
            facilities_with_ownership = [f for f in facilities if f.owned_by_school]
            if facilities_with_ownership:
                print(f"  Facilities with ownership: {len(facilities_with_ownership)}")
                for fac in facilities_with_ownership[:5]:  # Show first 5
                    print(f"    - {fac.name} → owned by '{fac.owned_by_school}'")

            
        except Exception as e:
            print(f"Error loading facilities: {e}")
            import traceback
            traceback.print_exc()
        
        self._facilities_cache = facilities
        return facilities
    
    
    def load_all_data(self) -> Tuple[List[Team], List[Facility], Dict]:
        print("=" * 60)
        print("Loading all data from Google Sheets...")
        print("=" * 60)
        
        rules = self.load_rules()
        
        # Load schools (includes tier, cluster, rivals, do-not-play, blackouts from TIERS_CLUSTERS sheet)
        schools = self.load_schools()
        
        # Load teams and facilities
        teams = self.load_teams()
        facilities = self.load_facilities()
            
        print("=" * 60)
        print(f"Data loading complete:")
        print(f"  - {len(schools)} schools")
        print(f"  - {len(teams)} teams")
        print(f"  - {len(facilities)} facilities")
        print(f"  - {len([s for s in schools.values() if s.blackout_dates])} schools with blackout dates")
        print(f"  - {len([s for s in schools.values() if s.rival_schools])} schools with rivals")
        print(f"  - {len([s for s in schools.values() if s.do_not_play_schools])} schools with do-not-play restrictions")
        print("=" * 60)
        
        return teams, facilities, rules
