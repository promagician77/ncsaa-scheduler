"""
Configuration constants for the NCSAA Basketball Scheduling System.
All configurable settings are defined here.
"""

from datetime import time
import os
import json
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

# Load environment variables from .env file
load_dotenv()

# Google Sheets Configuration
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "1vLzG_4nlYIlmm6iaVEJLt277PLlhvaWXbeR8Rj1xLTI")

# Credentials configuration
# Priority: GOOGLE_SHEETS_CREDENTIALS_JSON (env var) > GOOGLE_SHEETS_CREDENTIALS_FILE (env var) > default file path
CREDENTIALS_FILE = os.getenv(
    "GOOGLE_SHEETS_CREDENTIALS_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "credentials", "ncsaa-484512-3f8c48632375.json")
)
CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")  # JSON string from environment


def get_google_credentials() -> Credentials:
    """
    Get Google Sheets API credentials from environment variables or file.
    
    Priority:
    1. GOOGLE_SHEETS_CREDENTIALS_JSON (environment variable with JSON string)
    2. GOOGLE_SHEETS_CREDENTIALS_FILE (environment variable with file path)
    3. Default file path (for backward compatibility)
    
    Returns:
        Credentials object for Google Sheets API access
        
    Raises:
        ValueError: If no valid credentials are found
    """
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # Try JSON string from environment variable first (most secure)
    if CREDENTIALS_JSON:
        try:
            creds_dict = json.loads(CREDENTIALS_JSON)
            return Credentials.from_service_account_info(creds_dict, scopes=scopes)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Invalid JSON in GOOGLE_SHEETS_CREDENTIALS_JSON: {e}")
    
    # Try file path from environment variable or default
    if CREDENTIALS_FILE and os.path.exists(CREDENTIALS_FILE):
        return Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    
    # If neither works, raise an error
    raise ValueError(
        "Google Sheets credentials not found. Please set either:\n"
        "  - GOOGLE_SHEETS_CREDENTIALS_JSON (recommended): JSON string in environment variable\n"
        "  - GOOGLE_SHEETS_CREDENTIALS_FILE: Path to credentials JSON file\n"
        "  - Or place credentials file at default location"
    )

# Sheet Names
SHEET_DATES_NOTES = "DATES & NOTES"
SHEET_TIERS_CLUSTERS = "TIERS, CLUSTERS, RIVALS, DO NOT PLAY"
SHEET_TEAM_LIST = "WINTER BASKETBALL TEAM LIST"
SHEET_FACILITIES = "FACILITIES"
SHEET_COMPETITIVE_TIERS = "COMPETITIVE TIERS"
SHEET_BLACKOUTS = "WINTER BASKETBALL BLACKOUTS"
SHEET_WEEK_PREFIX = "26 WINTER WEEK"  # Prefix for weekly schedule sheets

# Scheduling Rules (Constants from the sheet)
SEASON_START_DATE = "2026-01-05"
SEASON_END_DATE = "2026-02-28"

# Game Time Rules
GAME_DURATION_MINUTES = 60
WEEKNIGHT_START_TIME = time(17, 0)  # 5:00 PM
WEEKNIGHT_END_TIME = time(20, 30)   # 8:30 PM
SATURDAY_START_TIME = time(8, 0)    # 8:00 AM
SATURDAY_END_TIME = time(18, 0)     # 6:00 PM
WEEKNIGHT_SLOTS = 3  # Must use all 3 game slots on weeknights

# Game Frequency Rules
MAX_GAMES_PER_7_DAYS = 2
MAX_GAMES_PER_14_DAYS = 3
MAX_DOUBLEHEADERS_PER_SEASON = 1
DOUBLEHEADER_BREAK_MINUTES = 60

# Holidays (No games on these dates)
US_HOLIDAYS = [
    "2026-01-19",  # Martin Luther King Jr. Day
    "2026-02-16"   # Presidents' Day
]

# Days of Week
NO_GAMES_ON_SUNDAY = True

# Division Names
DIVISIONS = [
    "ES K-1 REC",
    "ES 2-3 REC",
    "ES BOY'S COMP",
    "ES GIRL'S COMP",
    "BOY'S JV",
    "GIRL'S JV"
]

# Recreational Divisions (don't keep score, grouped together)
REC_DIVISIONS = ["ES K-1 REC", "ES 2-3 REC"]

# ES K-1 REC Special Rules
ES_K1_REC_RIM_HEIGHT = 8  # feet
ES_K1_REC_OFFICIALS = 1
ES_K1_REC_PRIORITY_SITES = [
    "Pinecrest Sloan Canyon K-1 Court",
    "Las Vegas Basketball Center",
    "Somerset Skye Canyon",
    "Freedom Classical"
]

# Competitive Tiers
TIERS = ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]

# Geographic Clusters
CLUSTERS = ["East", "West", "North", "Henderson"]

# Scheduling Priorities
PRIORITY_WEIGHTS = {
    "cluster_same_school": 100,   # Highest priority: cluster by school name
    "cluster_same_coach": 90,     # Second priority: cluster by coach
    "respect_rivals": 80,          # Required matchups
    "respect_do_not_play": 100,   # Must not schedule
    "geographic_cluster": 10000,   # CRITICAL: Prevent cross-town travel (increased from 300)
    "tier_matching": 400,          # CRITICAL: Competitive balance
    "facility_availability": 90,   # Must respect facility dates
    "game_frequency": 85,          # Respect max games rules
    "doubleheader_limit": 80,      # Respect doubleheader rules
    "home_away_balance": 50,       # Balance home/away games
    "weeknight_slots_full": 75     # Use all 3 weeknight slots
}

# Optimization Settings
MAX_ITERATIONS = 10000
TIMEOUT_SECONDS = 300  # 5 minutes
