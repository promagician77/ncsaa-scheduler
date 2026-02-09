from datetime import time
import os
import json
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "1vLzG_4nlYIlmm6iaVEJLt277PLlhvaWXbeR8Rj1xLTI")

CREDENTIALS_FILE = os.getenv(
    "GOOGLE_SHEETS_CREDENTIALS_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "credentials", "ncsaa-484512-3f8c48632375.json")
)
CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")


def get_google_credentials() -> Credentials:
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    if CREDENTIALS_JSON:
        try:
            creds_dict = json.loads(CREDENTIALS_JSON)
            return Credentials.from_service_account_info(creds_dict, scopes=scopes)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Invalid JSON in GOOGLE_SHEETS_CREDENTIALS_JSON: {e}")
    
    if CREDENTIALS_FILE and os.path.exists(CREDENTIALS_FILE):
        return Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    
    raise ValueError(
        "Google Sheets credentials not found. Please set either:\n"
        "  - GOOGLE_SHEETS_CREDENTIALS_JSON (recommended): JSON string in environment variable\n"
        "  - GOOGLE_SHEETS_CREDENTIALS_FILE: Path to credentials JSON file\n"
        "  - Or place credentials file at default location"
    )

SHEET_DATES_NOTES = "DATES & NOTES"
SHEET_TIERS_CLUSTERS = "TIERS, CLUSTERS, RIVALS, DO NOT PLAY"
SHEET_TEAM_LIST = "WINTER BASKETBALL TEAM LIST"
SHEET_FACILITIES = "FACILITIES"
SHEET_COMPETITIVE_TIERS = "COMPETITIVE TIERS"
SHEET_BLACKOUTS = "WINTER BASKETBALL BLACKOUTS"
SHEET_WEEK_PREFIX = "26 WINTER WEEK"  # Prefix for weekly schedule sheets

SEASON_START_DATE = "2026-01-05"
SEASON_END_DATE = "2026-02-28"
EIGHTH_GAME_CUTOFF_DATE = "2026-02-21"

GAME_DURATION_MINUTES = 60
WEEKNIGHT_START_TIME = time(17, 0)
WEEKNIGHT_END_TIME = time(20, 30)
SATURDAY_START_TIME = time(8, 0)
SATURDAY_END_TIME = time(18, 0)
WEEKNIGHT_SLOTS = 3

GAMES_PER_TEAM = 8

MAX_GAMES_PER_7_DAYS = 2
MAX_GAMES_PER_14_DAYS = 3
MAX_DOUBLEHEADERS_PER_SEASON = 1
DOUBLEHEADER_BREAK_MINUTES = 60

US_HOLIDAYS = [
    "2026-01-19",
    "2026-02-16"
]

NO_GAMES_ON_SUNDAY = True

DIVISIONS = [
    "ES K-1 REC",
    "ES 2-3 REC",
    "ES BOY'S COMP",
    "ES GIRL'S COMP",
    "BOY'S JV",
    "GIRL'S JV"
]

REC_DIVISIONS = ["ES K-1 REC", "ES 2-3 REC"]

ES_K1_REC_RIM_HEIGHT = 8
ES_K1_REC_OFFICIALS = 1
ES_K1_REC_PRIORITY_SITES = [
    "Pinecrest Sloan Canyon K-1 Court",
    "Las Vegas Basketball Center",
    "Somerset Skye Canyon",
    "Freedom Classical"
]

SATURDAY_PRIORITY_FACILITIES = [
    "Las Vegas Basketball Center",
    "Pinecrest Sloan Canyon",
    "Supreme Courtz"
]

SATURDAY_TARGET_FACILITIES = 4
SATURDAY_SECONDARY_FACILITIES = [
    "Somerset Skye Canyon",
    "Faith Christian"
]
    
TIERS = ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]

CLUSTERS = ["East", "West", "North", "Henderson"]

PRIORITY_WEIGHTS = {
    "school_consolidation": 150000,     
    "coach_consolidation": 200000,       
    "consecutive_slot_bonus": 100000,    
    
    "geographic_cluster": 10000,
    "tier_matching": 400,
    "respect_rivals": 80,
    
    # Constraints
    "cluster_same_school": 100,
    "cluster_same_coach": 90,
    "respect_do_not_play": 100,
    
    # Facility Optimization
    "saturday_priority_facility_fill": 200,
    "saturday_secondary_facility_fill": 100,
    "facility_availability": 90,
    
    # Other
    "game_frequency": 85,
    "doubleheader_limit": 80,
    "weeknight_slots_full": 75,
    "home_away_balance": 50
}

MAX_ITERATIONS = 10000
TIMEOUT_SECONDS = 300
