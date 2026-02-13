"""
Supabase data reader for the NCSAA Basketball Scheduling System.
Replaces Google Sheets integration with Supabase database.
"""

from datetime import datetime, date, time
from typing import List, Dict, Optional, Tuple
import os
from supabase import create_client, Client

from app.models import (
    Team, School, Facility, Division, Tier, Cluster,
    Schedule
)
from app.core.config import (
    SEASON_START_DATE, SEASON_END_DATE, US_HOLIDAYS
)

class SupabaseReader:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL", "https://qosxpkqedkszdodluusy.supabase.co")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFvc3hwa3FlZGtzemRvZGx1dXN5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA5MzczNjcsImV4cCI6MjA4NjUxMzM2N30.fg6eNAjjI-HpblmIhjYDjUtqmHlpqcKZ2fzQvXFs-iM")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        
        self._teams_cache: Optional[List[Team]] = None
        self._facilities_cache: Optional[List[Facility]] = None
        self._schools_cache: Optional[Dict[str, School]] = None
        self._rules_cache: Optional[Dict] = None
        self._clusters_cache: Optional[Dict[int, str]] = None
        self._divisions_cache: Optional[Dict[int, Dict]] = None
    
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
    
    def _parse_time(self, time_str: str) -> Optional[time]:
        if not time_str or time_str.strip() == '':
            return None
        
        time_str = time_str.strip()
        
        formats = [
            '%H:%M:%S',
            '%H:%M',
            '%I:%M %p',
            '%I:%M%p'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt).time()
            except ValueError:
                continue
        
        print(f"Warning: Could not parse time: {time_str}")
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
    
    def load_divisions(self) -> Dict[int, Dict]:
        if self._divisions_cache:
            return self._divisions_cache
        
        try:
            response = self.client.table('divisions').select('*').execute()
            divisions = {}
            
            for row in response.data:
                divisions[row['id']] = {
                    'name': row['name'],
                    'rec_div': row.get('rec_div', False),
                    'sex': row.get('sex'),
                    'level': row.get('level')
                }
            
            print(f"Loaded {len(divisions)} divisions from Supabase")
            self._divisions_cache = divisions
            return divisions
            
        except Exception as e:
            print(f"Error loading divisions: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def load_clusters(self) -> Dict[int, str]:
        if self._clusters_cache:
            return self._clusters_cache
        
        try:
            response = self.client.table('clusters').select('*').execute()
            clusters = {}
            
            for row in response.data:
                clusters[row['id']] = row['name']
            
            print(f"Loaded {len(clusters)} clusters from Supabase")
            self._clusters_cache = clusters
            return clusters
            
        except Exception as e:
            print(f"Error loading clusters: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def load_rules(self) -> Dict:
        if self._rules_cache:
            return self._rules_cache
        
        rules = {
            'season_start': self._parse_date(SEASON_START_DATE),
            'season_end': self._parse_date(SEASON_END_DATE),
            'holidays': [self._parse_date(h) for h in US_HOLIDAYS if self._parse_date(h)],
            'no_game_dates': [],
            'notes': []
        }
        
        self._rules_cache = rules
        print(f"Loaded rules: {rules['season_start']} to {rules['season_end']}, {len(rules['holidays'])} holidays")
        return rules
    
    def load_schools(self) -> Dict[str, School]:
        if self._schools_cache:
            return self._schools_cache
        
        schools = {}
        
        try:
            clusters = self.load_clusters()
            response = self.client.table('schools').select('*, clusters(name)').execute()
            
            school_id_to_name = {}
            for row in response.data:
                school_id_to_name[row['id']] = row['name']
            
            for row in response.data:
                school_name = row['name']
                
                tier = None
                if row.get('tier'):
                    tier = self._parse_enum(f"Tier {row['tier']}", Tier)
                
                cluster = None
                if row.get('clusters') and row['clusters'].get('name'):
                    cluster_name = row['clusters']['name']
                    cluster = self._parse_enum(cluster_name, Cluster)
                elif row.get('cluster') and row['cluster'] in clusters:
                    cluster_name = clusters[row['cluster']]
                    cluster = self._parse_enum(cluster_name, Cluster)
                
                rival_schools = set()
                if row.get('rivals') and isinstance(row['rivals'], list):
                    for rival_id in row['rivals']:
                        if rival_id in school_id_to_name:
                            rival_schools.add(school_id_to_name[rival_id])
                
                do_not_play_schools = set()
                if row.get('do_not_play') and isinstance(row['do_not_play'], list):
                    for dnp_id in row['do_not_play']:
                        if dnp_id in school_id_to_name:
                            do_not_play_schools.add(school_id_to_name[dnp_id])
                
                blackout_dates = []
                if row.get('blackouts') and isinstance(row['blackouts'], list):
                    for blackout_str in row['blackouts']:
                        blackout_date = self._parse_date(blackout_str)
                        if blackout_date:
                            blackout_dates.append(blackout_date)
                
                schools[school_name] = School(
                    name=school_name,
                    cluster=cluster,
                    tier=tier,
                    blackout_dates=blackout_dates,
                    rival_schools=rival_schools,
                    do_not_play_schools=do_not_play_schools 
                )
            
            print(f"Loaded {len(schools)} schools from Supabase")
            print(f"  - {len([s for s in schools.values() if s.rival_schools])} schools with rivals")
            print(f"  - {len([s for s in schools.values() if s.do_not_play_schools])} schools with do-not-play restrictions")
            print(f"  - {len([s for s in schools.values() if s.blackout_dates])} schools with blackout dates")
            print(f"  - {len([s for s in schools.values() if s.cluster])} schools with clusters")
            print(f"  - {len([s for s in schools.values() if s.tier])} schools with tiers")
            
        except Exception as e:
            print(f"Error loading schools: {e}")
            import traceback
            traceback.print_exc()
        
        self._schools_cache = schools
        return schools
    
    def load_teams(self) -> List[Team]:
        if self._teams_cache:
            return self._teams_cache
        schools = self.load_schools()
        facilities = self.load_facilities()  # Load facilities first
        teams = []
        
        # Create a mapping of school name -> home facility name
        school_to_facility = {}
        for facility in facilities:
            if facility.owned_by_school:
                school_to_facility[facility.owned_by_school] = facility.name
        
        print(f"School to facility mapping: {len(school_to_facility)} schools have home facilities")
        
        try:
            response = self.client.table('teams').select('*, schools(*), divisions(*)').execute()

            for row in response.data:
                school_data = row.get('schools')
                if not school_data:
                    print(f"Warning: Team {row['id']} has no school data")
                    continue
                
                school_name = school_data['name']
                
                if school_name not in schools:
                    tier = None
                    cluster = None
                    rival_schools = set()
                    do_not_play_schools = set()
                    blackout_dates = []
                    
                    if school_data.get('tier'):
                        tier = self._parse_enum(f"Tier {school_data['tier']}", Tier)
                    
                    if school_data.get('cluster'):
                        clusters = self.load_clusters()
                        if school_data['cluster'] in clusters:
                            cluster_name = clusters[school_data['cluster']]
                            cluster = self._parse_enum(cluster_name, Cluster)
                    
                    schools[school_name] = School(
                        name=school_name,
                        cluster=cluster,
                        tier=tier,
                        blackout_dates=blackout_dates,
                        rival_schools=rival_schools,
                        do_not_play_schools=do_not_play_schools
                    )
                
                school = schools[school_name]
                
                division_data = row.get('divisions')
                if not division_data:
                    print(f"Warning: Team {row['id']} has no division data")
                    continue
                
                division_name = division_data.get('name')
                if not division_name:
                    print(f"Warning: Team {row['id']} has division but no name")
                    continue
                
                division = self._parse_enum(division_name, Division)
                if not division:
                    print(f"Warning: Could not parse division '{division_name}' for team {row['id']}")
                    continue
                
                # Get home facility from the school-to-facility mapping
                home_facility = school_to_facility.get(school_name)
                
                team = Team(
                    id=str(row['id']),
                    school=school,
                    division=division,
                    coach_name=row.get('coach', ''),
                    home_facility=home_facility,  # Now properly assigned from facilities
                    tier=school.tier,
                    cluster=school.cluster
                )
                
                teams.append(team)
            
            print(f"Loaded {len(teams)} teams from Supabase")
            
            # Build a mapping of school name -> list of team IDs
            school_to_team_ids = {}
            for team in teams:
                school_name = team.school.name
                if school_name not in school_to_team_ids:
                    school_to_team_ids[school_name] = []
                school_to_team_ids[school_name].append(team.id)
            
            # Now populate rivals and do_not_play for each team based on school relationships
            for team in teams:
                # Get rival team IDs from rival schools
                for rival_school_name in team.school.rival_schools:
                    if rival_school_name in school_to_team_ids:
                        team.rivals.update(school_to_team_ids[rival_school_name])
                
                # Get do-not-play team IDs from do-not-play schools
                for dnp_school_name in team.school.do_not_play_schools:
                    if dnp_school_name in school_to_team_ids:
                        team.do_not_play.update(school_to_team_ids[dnp_school_name])
            
            division_counts = {}
            for team in teams:
                div = team.division.value
                division_counts[div] = division_counts.get(div, 0) + 1
            
            print(f"  Teams by division:")
            for div, count in sorted(division_counts.items()):
                print(f"    - {div}: {count} teams")
            
            # Print teams with home facilities
            teams_with_facilities = [t for t in teams if t.home_facility]
            print(f"  Teams with home facilities: {len(teams_with_facilities)}/{len(teams)}")
            
            # Print rivalry statistics
            teams_with_rivals = [t for t in teams if t.rivals]
            teams_with_dnp = [t for t in teams if t.do_not_play]
            print(f"  Teams with rivals: {len(teams_with_rivals)}")
            print(f"  Teams with do-not-play restrictions: {len(teams_with_dnp)}")
            
        except Exception as e:
            print(f"Error loading teams: {e}")
            import traceback
            traceback.print_exc()
        
        self._teams_cache = teams
        return teams
    
    def load_facilities(self) -> List[Facility]:
        if self._facilities_cache:
            return self._facilities_cache
        
        facilities = []
        
        try:    
            response = self.client.table('facilities').select('*, schools(name)').execute()
            
            for row in response.data:
                facility_name = row['name']
                
                available_dates = []
                if row.get('dates') and isinstance(row['dates'], list):
                    for date_str in row['dates']:
                        parsed_date = self._parse_date(date_str)
                        if parsed_date:
                            available_dates.append(parsed_date)
                
                max_courts = 1
                if row.get('court') and isinstance(row['court'], list):
                    max_courts = len(row['court'])
                elif row.get('court'):
                    max_courts = 1
                
                if row.get('start_time'):
                    if isinstance(row['start_time'], str):
                        start_time = self._parse_time(row['start_time'])
                    else:
                        start_time = row['start_time']
                
                if row.get('end_time'):
                    if isinstance(row['end_time'], str):
                        end_time = self._parse_time(row['end_time'])
                    else:
                        end_time = row['end_time']
                
                allowed_divisions = []
                if row.get('allowed_div') and isinstance(row['allowed_div'], list):
                    allowed_divisions = row['allowed_div']
                
                owned_by_school = None
                if row.get('schools') and row['schools'].get('name'):
                    owned_by_school = row['schools']['name']
                
                has_8ft_rims = False
                if allowed_divisions:
                    for div in allowed_divisions:
                        if 'K-1' in str(div) or 'k-1' in str(div).lower():
                            has_8ft_rims = True
                            break
                
                facility = Facility(
                    name=facility_name,
                    address=facility_name,
                    available_dates=available_dates,
                    max_courts=max_courts,
                    has_8ft_rims=has_8ft_rims,
                    owned_by_school=owned_by_school
                )
                
                facilities.append(facility)
            
            print(f"Loaded {len(facilities)} facilities from Supabase")
            
            facilities_with_dates = [f for f in facilities if f.available_dates]
            facilities_without_dates = [f for f in facilities if not f.available_dates]
            
            print(f"  - Facilities with specific dates: {len(facilities_with_dates)}")
            print(f"  - Facilities available all season: {len(facilities_without_dates)}")
            
            facilities_with_ownership = [f for f in facilities if f.owned_by_school]
            if facilities_with_ownership:
                print(f"  - Facilities with ownership: {len(facilities_with_ownership)}")
                for fac in facilities_with_ownership[:5]:
                    print(f"    → {fac.name} owned by '{fac.owned_by_school}'")
            
            multi_court_facilities = [f for f in facilities if f.max_courts > 1]
            if multi_court_facilities:
                print(f"  - Facilities with multiple courts: {len(multi_court_facilities)}")
                for fac in multi_court_facilities[:5]:
                    print(f"    → {fac.name}: {fac.max_courts} courts")
            
        except Exception as e:
            print(f"Error loading facilities: {e}")
            import traceback
            traceback.print_exc()
        
        self._facilities_cache = facilities
        return facilities
    
    def load_all_data(self) -> Tuple[List[Team], List[Facility], Dict]:
        print("=" * 60)
        print("Loading all data from Supabase...")
        print("=" * 60)
        
        rules = self.load_rules()
        divisions = self.load_divisions()
        clusters = self.load_clusters()
        schools = self.load_schools()
        teams = self.load_teams()
        facilities = self.load_facilities()
            
        print("=" * 60)
        print(f"Data loading complete:")
        print(f"  - {len(divisions)} divisions")
        print(f"  - {len(clusters)} clusters")
        print(f"  - {len(schools)} schools")
        print(f"  - {len(teams)} teams")
        print(f"  - {len(facilities)} facilities")
        print(f"\nSchool Relationships:")
        print(f"  - {len([s for s in schools.values() if s.blackout_dates])} schools with blackout dates")
        print(f"  - {len([s for s in schools.values() if s.rival_schools])} schools with rivals")
        print(f"  - {len([s for s in schools.values() if s.do_not_play_schools])} schools with do-not-play restrictions")
        print(f"  - {len([s for s in schools.values() if s.cluster])} schools assigned to clusters")
        print(f"  - {len([s for s in schools.values() if s.tier])} schools assigned to tiers")
        print("=" * 60)
        
        return teams, facilities, rules
    
    def clear_caches(self):
        self._teams_cache = None
        self._facilities_cache = None
        self._schools_cache = None
        self._rules_cache = None
        self._clusters_cache = None
        self._divisions_cache = None

        print("All caches cleared")