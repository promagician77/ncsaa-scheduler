from datetime import time
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://qosxpkqedkszdodluusy.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFvc3hwa3FlZGtzemRvZGx1dXN5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA5MzczNjcsImV4cCI6MjA4NjUxMzM2N30.fg6eNAjjI-HpblmIhjYDjUtqmHlpqcKZ2fzQvXFs-iM")

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
