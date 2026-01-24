"""
Configuration constants for the NCSAA Basketball Scheduling System.
All configurable settings are defined here.
"""

from datetime import time

# Google Sheets Configuration
SPREADSHEET_ID = "1vLzG_4nlYIlmm6iaVEJLt277PLlhvaWXbeR8Rj1xLTI"
CREDENTIALS_FILE = "ncsaa-484512-3f8c48632375.json"

# Sheet Names
SHEET_DATES_NOTES = "DATES & NOTES"
SHEET_TIERS_CLUSTERS = "TIERS, CLUSTERS, RIVALS, DO NOT PLAY"
SHEET_TEAM_LIST = "WINTER BASKETBALL TEAM LIST"
SHEET_FACILITIES = "FACILITIES"
SHEET_COMPETITIVE_TIERS = "COMPETITIVE TIERS"
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
    "cluster_same_school": 100,  # Highest priority: cluster by school name
    "cluster_same_coach": 90,    # Second priority: cluster by coach
    "respect_rivals": 80,         # Required matchups
    "respect_do_not_play": 100,  # Must not schedule
    "tier_matching": 70,          # Prefer same tier matchups
    "geographic_cluster": 60,     # Prefer same geographic area
    "facility_availability": 90,  # Must respect facility dates
    "game_frequency": 85,         # Respect max games rules
    "doubleheader_limit": 80,     # Respect doubleheader rules
    "home_away_balance": 50,      # Balance home/away games
    "weeknight_slots_full": 75    # Use all 3 weeknight slots
}

# Optimization Settings
MAX_ITERATIONS = 10000
TIMEOUT_SECONDS = 300  # 5 minutes
