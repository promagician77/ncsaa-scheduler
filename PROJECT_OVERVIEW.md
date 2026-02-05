# NCSAA Basketball Scheduling System - Complete Project Overview

## 🏀 Project Purpose

The **NCSAA Basketball Scheduling System** is a sophisticated scheduling application designed to automatically generate optimized basketball game schedules for the Nevada Coalition for School Activities and Athletics (NCSAA). The system handles complex scheduling constraints, team clustering, facility management, and creates schedules that minimize travel while respecting competitive balance and organizational rules.

---

## 📊 System Architecture

The project consists of **three main components**:

### 1. **Backend API** (FastAPI - Python)
- **Location**: `/root/ncsaa-scheduler/`
- **Technology Stack**:
  - FastAPI for REST API
  - Python 3.12+
  - Google Sheets API (gspread)
  - OR-Tools for constraint optimization
  - Celery for async task processing
  - Redis for task queue management

### 2. **Frontend Web UI** (Next.js - TypeScript)
- **Location**: `/root/ncsaa-scheduler-frontend/`
- **Technology Stack**:
  - Next.js 16.1.4 (React 19)
  - TypeScript
  - Tailwind CSS for styling
  - Modern, responsive design

### 3. **Data Source** (Google Sheets)
- **Integration**: Google Sheets API with service account authentication
- **Purpose**: Centralized data management for teams, facilities, rules, and constraints
- **Benefits**: Non-technical staff can update data without coding

---

## 🎯 Core Features

### Schedule Generation
1. **Intelligent Team Clustering**
   - Groups games by **school matchups** (not just divisions)
   - Ensures coaches with multiple teams play **back-to-back games**
   - Implements **"Most Important Rule #15"**: Schools clustered by name, then coach
   - Minimizes travel by respecting **geographic clusters** (East, West, North, Henderson)

2. **Complex Constraint Handling**
   - **Time Constraints**: Weeknight (5-8:30 PM) and Saturday (8 AM-6 PM) slots
   - **Game Frequency**: Max 2 games per 7 days, 3 per 14 days
   - **Facility Availability**: Respects blackout dates and venue limitations
   - **Division-Specific Rules**: Special handling for ES K-1 REC (8-foot rims, 1 official)
   - **Competitive Tiers**: Matches teams within similar skill levels (Tier 1-4)
   - **Rivals & Do-Not-Play**: Enforces required matchups and prohibits specific pairings

3. **Optimization Algorithm**
   - Uses **weighted priority system** with 11 different constraint types
   - Critical weights:
     - Geographic clustering: **10,000** (prevent cross-town travel)
     - Tier matching: **400** (competitive balance)
     - Do-not-play rules: **100** (hard constraint)
   - Generates time blocks for consecutive games on same court
   - Maximizes facility utilization (client feedback: "use 8-10 hour slots efficiently")

### Data Management
- **Real-time Google Sheets integration**
- **8 sheets** parsed for comprehensive data:
  1. `DATES & NOTES` - Season rules and holidays
  2. `TIERS, CLUSTERS, RIVALS, DO NOT PLAY` - Team relationships
  3. `WINTER BASKETBALL TEAM LIST` - Team roster with coach info
  4. `FACILITIES` - Venue availability and specifications
  5. `COMPETITIVE TIERS` - Skill level assignments
  6. `WINTER BASKETBALL BLACKOUTS` - School-specific unavailable dates
  7. Weekly schedule sheets (e.g., `26 WINTER WEEK 1-8`)
  8. Additional configuration sheets

### Validation & Quality Control
- **Multi-level validation**:
  - Hard constraint violations (must fix)
  - Soft constraint violations (warnings)
  - Penalty scoring system
- **Statistics tracking**:
  - Games per team
  - Home/away balance
  - Facility utilization
  - Constraint compliance

### User Interface
- **Modern, responsive web interface**
- **Two main views**:
  1. **Schedule View**: Generate and display schedules
  2. **Information View**: View loaded data (teams, facilities, rules)
- **Features**:
  - One-click schedule generation
  - Real-time progress tracking (async processing)
  - Game filtering and search
  - Export capabilities
  - Dark mode support

---

## 📁 Project Structure

```
/root/
├── ncsaa-scheduler/              # Backend (FastAPI)
│   ├── app/
│   │   ├── main.py               # FastAPI app entry point
│   │   ├── api/
│   │   │   └── routes.py         # API endpoints
│   │   ├── core/
│   │   │   ├── config.py         # Configuration (NOW env-based!)
│   │   │   └── celery_app.py    # Celery configuration
│   │   ├── models/
│   │   │   └── models.py         # Data models (Team, Game, Facility, etc.)
│   │   ├── services/
│   │   │   ├── scheduler_v2.py   # School-based scheduler (ACTIVE)
│   │   │   ├── scheduler.py      # Original scheduler (deprecated)
│   │   │   ├── sheets_reader.py  # Google Sheets data loader
│   │   │   └── validator.py      # Schedule validation
│   │   └── tasks/
│   │       └── scheduler_tasks.py # Celery async tasks
│   ├── scripts/
│   │   ├── run_api.py            # Start API server
│   │   ├── run_scheduler.py      # CLI scheduler
│   │   └── run_celery_worker.py  # Start Celery worker
│   ├── credentials/              # Google Sheets API credentials
│   ├── .env                      # Environment variables (SECRET!)
│   ├── .env.example              # Template for configuration
│   └── requirements.txt          # Python dependencies
│
└── ncsaa-scheduler-frontend/     # Frontend (Next.js)
    ├── app/
    │   ├── page.tsx              # Main page
    │   ├── layout.tsx            # Root layout
    │   ├── globals.css           # Global styles
    │   └── components/
    │       ├── ScheduleGenerator.tsx  # Generate button & controls
    │       ├── ScheduleDisplay.tsx    # Display generated schedule
    │       ├── DataDisplay.tsx        # Display loaded data
    │       ├── ScheduleStats.tsx      # Statistics display
    │       ├── ScheduleInfo.tsx       # Info cards
    │       └── GameCard.tsx           # Individual game card
    ├── package.json              # Node dependencies
    └── tsconfig.json             # TypeScript config
```

---

## 🔧 Key Technologies & Dependencies

### Backend Dependencies
```
google-auth==2.27.0              # Google authentication
gspread==6.0.0                   # Google Sheets API client
ortools==9.8.3296                # Constraint optimization
fastapi==0.115.6                 # Modern web framework
uvicorn[standard]==0.34.0        # ASGI server
celery==5.4.0                    # Async task queue
redis==5.2.1                     # Task queue backend
python-dotenv==1.0.0             # Environment variable management
pydantic==2.5.3                  # Data validation
```

### Frontend Dependencies
```
next@16.1.4                      # React framework
react@19.2.3                     # UI library
tailwindcss@4                    # Utility-first CSS
typescript@5                     # Type safety
```

---

## 🎨 Data Models

### Core Entities

#### **Team**
- `id`: Unique identifier (e.g., "Doral Academy Palo Verde K-1 Rec")
- `school`: School object (name, cluster, tier)
- `division`: Division enum (ES K-1 REC, ES BOY'S COMP, etc.)
- `coach_name`, `coach_email`: Contact information
- `home_facility`: Preferred venue
- `rivals`: Set of team IDs that should play each other
- `do_not_play`: Set of team IDs that must NOT play each other
- `tier`: Competitive level (Tier 1-4)
- `cluster`: Geographic region (East, West, North, Henderson)

#### **Facility**
- `name`: Venue name
- `address`: Physical location
- `available_dates`: List of dates venue is available
- `unavailable_dates`: Blackout dates
- `max_courts`: Number of courts (for parallel games)
- `has_8ft_rims`: Special requirement for ES K-1 REC

#### **Game**
- `id`: Unique game identifier
- `home_team`, `away_team`: Team objects
- `time_slot`: TimeSlot object (date, time, facility, court)
- `division`: Division enum
- `is_doubleheader`: Boolean flag
- `officials_count`: Number of referees needed

#### **Schedule**
- `games`: List of Game objects
- `season_start`, `season_end`: Date range
- Methods: `get_team_games()`, `get_games_by_date()`, etc.

---

## 🚀 API Endpoints

### Health Check
```
GET /api/health
Response: {"status": "healthy", "timestamp": "2026-02-04T..."}
```

### Generate Schedule (Synchronous)
```
POST /api/schedule
Body: {"force_regenerate": false}
Response: {
  "success": true,
  "message": "Schedule generated successfully with 450 games",
  "total_games": 450,
  "games": [...],
  "validation": {...},
  "generation_time": 12.5
}
```

### Generate Schedule (Asynchronous)
```
POST /api/schedule/async
Response: {"task_id": "abc-123", "status": "PENDING"}

GET /api/schedule/status/{task_id}
Response: {"status": "SUCCESS", "result": {...}}
```

### Get Statistics
```
GET /api/stats
Response: {
  "total_teams": 75,
  "total_games": 450,
  "games_by_division": {...},
  "teams_with_8_games": 60,
  "teams_under_8_games": 10,
  "teams_over_8_games": 5
}
```

---

## ⚙️ Configuration System (Environment Variables)

### **RECENT UPDATE**: All configuration now uses environment variables!

The system loads configuration from `.env` file with these categories:

#### Google Sheets Configuration
```bash
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_SHEETS_CREDENTIALS_JSON={"type":"service_account",...}  # For deployment
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials/file.json           # For local dev
```

#### Schedule Rules
```bash
SEASON_START_DATE=2026-01-05
SEASON_END_DATE=2026-02-28
US_HOLIDAYS=2026-01-19,2026-02-16  # MLK Day, Presidents' Day
NO_GAMES_ON_SUNDAY=true
```

#### Game Time Rules
```bash
GAME_DURATION_MINUTES=60
WEEKNIGHT_START_TIME=17:00
WEEKNIGHT_END_TIME=20:30
SATURDAY_START_TIME=08:00
SATURDAY_END_TIME=18:00
WEEKNIGHT_SLOTS=3
```

#### Game Frequency Rules
```bash
MAX_GAMES_PER_7_DAYS=2
MAX_GAMES_PER_14_DAYS=3
MAX_DOUBLEHEADERS_PER_SEASON=1
DOUBLEHEADER_BREAK_MINUTES=60
```

#### Priority Weights (Optimization)
```bash
PRIORITY_GEOGRAPHIC_CLUSTER=10000  # CRITICAL: Prevent cross-town travel
PRIORITY_TIER_MATCHING=400         # CRITICAL: Competitive balance
PRIORITY_CLUSTER_SAME_SCHOOL=100
PRIORITY_RESPECT_DO_NOT_PLAY=100
# ... more weights
```

---

## 🔄 Scheduling Algorithm (SchoolBasedScheduler)

### Core Philosophy
**"Schedule by school matchups, not by divisions"**

When Doral Red Rock plays Doral Saddle, ALL divisions (K-1 Rec, Boys Comp, Girls Comp, JV) should play **back-to-back** on the **same night**, at the **same facility**, on **consecutive courts/times**.

### Algorithm Steps

1. **Group Teams by School**
   - Identify unique schools
   - Group all teams (across divisions) by school

2. **Generate School Matchups**
   - Create pairings: School A vs School B
   - For each matchup, find all division games between schools
   - Example: Doral Red Rock vs Doral Saddle might have 3 games (K-1 Rec, Boys JV, Girls JV)

3. **Create Time Blocks**
   - Generate consecutive time slots on **same court**
   - NOT parallel slots across courts
   - Example: Court 1 at 5:00 PM, 6:00 PM, 7:00 PM (consecutive)

4. **Schedule Matchups**
   - Allocate time blocks that fit all games for a matchup
   - Prioritize:
     - Geographic proximity (same cluster)
     - Tier matching (competitive balance)
     - Facility availability
     - Respect blackout dates
     - Minimize weeknight spread

5. **Coach Clustering**
   - Coaches with multiple teams get **consecutive games**
   - Example: Coach Sarah with K-1 and 2-3 teams plays at 5 PM and 6 PM

6. **Validation & Refinement**
   - Check all constraints
   - Calculate penalty scores
   - Report violations

### Key Features
- **Geographic Clustering**: Weight of 10,000 (highest priority)
- **One Facility Per School Per Night**: No splitting schools across venues
- **Minimize Weeknights**: Schools play on as few weeknights as possible
- **Maximize Facility Usage**: Fill 8-10 hour blocks efficiently
- **Back-to-Back Games**: Coaches don't wait between games

---

## 📊 Scheduling Constraints

### Hard Constraints (Must Satisfy)
1. **Time Conflicts**: No team plays simultaneously
2. **Facility Availability**: Only schedule at available venues
3. **Do-Not-Play Rules**: Never schedule prohibited matchups
4. **Holiday Restrictions**: No games on US holidays
5. **Weeknight Slots**: Must fill all 3 slots on weeknights

### Soft Constraints (Optimize)
1. **Geographic Clustering**: Minimize cross-town travel
2. **Tier Matching**: Match competitive skill levels
3. **Home/Away Balance**: Distribute fairly
4. **Game Frequency**: Respect max games per period
5. **Doubleheader Limits**: Max 1 doubleheader per season
6. **Facility Preferences**: Use priority sites for ES K-1 REC

---

## 🏗️ How Data Flows

### Schedule Generation Flow
```
1. User clicks "Generate Schedule" in UI
   ↓
2. Frontend sends POST to /api/schedule
   ↓
3. Backend loads data from Google Sheets (SheetsReader)
   - Teams (75+ teams across 6 divisions)
   - Facilities (10+ venues)
   - Rules (seasons, holidays, blackouts)
   - Relationships (rivals, do-not-play, tiers, clusters)
   ↓
4. SchoolBasedScheduler processes data
   - Groups teams by school
   - Generates time blocks
   - Creates school matchups
   - Optimizes schedule (OR-Tools)
   ↓
5. ScheduleValidator checks constraints
   - Hard violations
   - Soft violations
   - Penalty scores
   ↓
6. API returns schedule to frontend
   - 450+ games
   - Validation results
   - Statistics
   ↓
7. Frontend displays schedule
   - Filterable game list
   - Statistics dashboard
   - Validation summary
```

### Async Processing Flow (for long operations)
```
1. User clicks "Generate Schedule"
   ↓
2. Frontend sends POST to /api/schedule/async
   ↓
3. Celery task starts in background
   ↓
4. Frontend polls GET /api/schedule/status/{task_id}
   ↓
5. Shows progress: "Loading data..." → "Generating..." → "Validating..."
   ↓
6. When complete, displays result
```

---

## 🎯 Business Rules & Special Cases

### Division-Specific Rules

#### ES K-1 REC
- **Rim Height**: 8 feet (requires `has_8ft_rims=true` facilities)
- **Officials**: 1 referee only
- **Priority Sites**: 
  - Pinecrest Sloan Canyon K-1 Court
  - Las Vegas Basketball Center
  - Somerset Skye Canyon
  - Freedom Classical

#### ES 2-3 REC
- Recreational (no scorekeeping)
- Grouped with K-1 REC for scheduling

#### Competitive Divisions
- ES BOY'S COMP, ES GIRL'S COMP
- BOY'S JV, GIRL'S JV
- Tier-based matchmaking (Tier 1-4)
- Rivalries enforced

### Geographic Clusters
- **East**: Eastern Las Vegas schools
- **West**: Western Las Vegas schools
- **North**: North Las Vegas schools
- **Henderson**: Henderson area schools

**Goal**: Minimize travel by keeping clusters together

### Coaching Scenarios
- **Multi-Team Coaches**: Back-to-back games (e.g., 5 PM K-1, 6 PM 2-3)
- **School Clustering**: All teams from same school play same night
- **Example**: Doral Red Rock has 4 teams → all 4 games vs same opponent school, same night, consecutive times

---

## 🚀 How to Run the System

### Prerequisites
```bash
# Backend
- Python 3.12+
- Redis server (for Celery)
- Google Sheets API credentials

# Frontend
- Node.js 20+
- npm or yarn
```

### Backend Setup
```bash
cd /root/ncsaa-scheduler

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Google Sheets credentials

# Run API server
uvicorn app.main:app --port 8001 --reload

# OR use script
python scripts/run_api.py

# Run Celery worker (for async tasks)
python scripts/run_celery_worker.py
```

### Frontend Setup
```bash
cd /root/ncsaa-scheduler-frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Access at http://localhost:3000
```

### CLI Schedule Generation
```bash
cd /root/ncsaa-scheduler

# Generate and write to Google Sheets
python scripts/run_scheduler.py

# Generate without writing (preview)
python scripts/run_scheduler.py --no-write

# Verbose output
python scripts/run_scheduler.py --verbose
```

---

## 📈 Performance & Scalability

### Current Capacity
- **Teams**: 75+ teams across 6 divisions
- **Games**: 450+ games per season
- **Facilities**: 10+ venues
- **Generation Time**: 10-15 seconds (synchronous)

### Optimization Techniques
1. **Caching**: Google Sheets data cached in memory
2. **Async Processing**: Long operations handled by Celery
3. **Constraint Pruning**: Early elimination of invalid slots
4. **Weighted Priorities**: Focus on critical constraints first
5. **Time Block Allocation**: Batch processing instead of individual slots

### Bottlenecks
- **Google Sheets API**: Rate limits on reads/writes
- **Constraint Optimization**: NP-hard problem, exponential complexity
- **Data Quality**: Missing cluster/tier assignments limit optimization

---

## 🐛 Common Issues & Solutions

### Issue: "Python-dotenv could not parse statement"
**Cause**: Multi-line JSON in `.env` file  
**Solution**: Use file path method or single-line JSON
```bash
# Use file path (recommended for local)
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials/file.json

# OR single-line JSON (for deployment)
GOOGLE_SHEETS_CREDENTIALS_JSON='{"type":"service_account",...}'
```

### Issue: "Cluster coverage low (< 90%)"
**Cause**: Teams missing cluster assignments in Google Sheets  
**Solution**: Update "TIERS, CLUSTERS, RIVALS, DO NOT PLAY" sheet with cluster values

### Issue: "Cross-town travel violations"
**Cause**: Not enough teams in same cluster to match  
**Solution**: Review cluster assignments, may need to relax geographic constraint

### Issue: "Facility not available"
**Cause**: Blackout dates or facility constraints  
**Solution**: Check "FACILITIES" and "WINTER BASKETBALL BLACKOUTS" sheets

---

## 🔮 Future Enhancements

### Planned Features
1. **Real-time Collaboration**: Multiple users editing schedule simultaneously
2. **Mobile App**: Native iOS/Android apps
3. **Email Notifications**: Auto-send schedules to coaches
4. **Conflict Resolution**: Interactive UI for fixing violations
5. **Historical Analysis**: Season-over-season comparison
6. **Facility Management**: Integration with venue booking systems
7. **Referee Scheduling**: Auto-assign officials to games
8. **Team Portal**: Coaches can view their schedules, request changes

### Technical Improvements
1. **Machine Learning**: Learn from past schedules to improve optimization
2. **WebSocket Updates**: Real-time schedule generation progress
3. **Database Backend**: PostgreSQL for faster queries (vs Google Sheets)
4. **Microservices**: Separate scheduling engine from API
5. **Kubernetes**: Container orchestration for scalability
6. **GraphQL API**: More flexible data queries

---

## 📚 Key Learnings & Design Decisions

### Why School-Based Scheduling?
**Original Problem**: Division-based scheduling spread schools across multiple nights  
**Client Feedback**: "Coaches come to gym on 3 different nights for 3 different teams"  
**Solution**: School matchups ensure all games for a school happen on one night  
**Result**: Dramatically reduced travel and improved coach satisfaction

### Why Google Sheets Integration?
**Alternative**: Database-driven system  
**Chosen**: Google Sheets API  
**Reason**: Non-technical staff can update data without developer intervention  
**Trade-off**: Slower than database, but much more flexible for client

### Why Weighted Constraints?
**Alternative**: Hard-coded rule priorities  
**Chosen**: Configurable priority weights in `.env`  
**Reason**: Easy to tune without code changes  
**Example**: `PRIORITY_GEOGRAPHIC_CLUSTER=10000` can be adjusted to 5000 if needed

### Why Celery for Async?
**Alternative**: Built-in FastAPI background tasks  
**Chosen**: Celery + Redis  
**Reason**: Better for long-running tasks, supports task monitoring, can scale horizontally  
**Trade-off**: More complex setup, but production-ready

---

## 🤝 Contributing & Maintenance

### Code Style
- **Python**: PEP 8, type hints, docstrings
- **TypeScript**: ESLint, Prettier, strict mode
- **Comments**: Explain "why", not "what"

### Testing
- **Unit Tests**: Test individual functions
- **Integration Tests**: Test API endpoints
- **Validation Tests**: Test constraint checking

### Deployment Checklist
1. Update `.env` with production credentials
2. Set `GOOGLE_SHEETS_CREDENTIALS_JSON` (not file path)
3. Configure Redis connection
4. Set CORS origins to production domain
5. Enable HTTPS
6. Set up monitoring (error tracking, performance)
7. Configure backup strategy for Google Sheets data

---

## 📞 Support & Documentation

### Documentation Files
- `README.md`: Quick start guide
- `PROJECT_OVERVIEW.md`: This comprehensive document
- `.env.example`: Configuration template
- API docs: http://localhost:8001/docs (when server running)

### Key Contacts
- **Client**: NCSAA (Nevada Coalition for School Activities and Athletics)
- **Primary Use Case**: Winter basketball season scheduling

### Important Links
- Google Sheets: Configured in `GOOGLE_SHEETS_SPREADSHEET_ID`
- API Server: http://localhost:8001 (development)
- Frontend: http://localhost:3000 (development)

---

## 🎓 Technical Concepts

### Constraint Programming
The scheduler uses **constraint satisfaction problem (CSP)** techniques:
- **Variables**: Game slots (time, facility, court)
- **Domains**: Possible values for each variable
- **Constraints**: Rules that limit combinations
- **Objective**: Minimize penalty score (weighted sum of violations)

### Time Complexity
- **Best Case**: O(n log n) with perfect data (no conflicts)
- **Average Case**: O(n² × m) where n=teams, m=time slots
- **Worst Case**: O(2^n) (exponential, NP-hard)
- **Optimization**: Use heuristics to prune search space

### Data Structures
- **Sets**: Fast membership testing (O(1))
- **Defaultdicts**: Automatic initialization
- **Dataclasses**: Type-safe, self-documenting models
- **Enums**: Type-safe constants

---

## 🏁 Conclusion

The NCSAA Basketball Scheduling System is a comprehensive solution that transforms a complex, manual scheduling process into an automated, optimized system. By leveraging modern web technologies, constraint programming, and intelligent algorithms, it generates schedules that:

✅ Minimize travel time for teams and coaches  
✅ Respect complex organizational rules  
✅ Ensure competitive balance  
✅ Maximize facility utilization  
✅ Provide flexibility for changes  
✅ Offer user-friendly interfaces for all stakeholders  

The system represents a significant improvement over manual scheduling, saving hundreds of hours of work while producing higher-quality schedules that better serve students, coaches, and families.

---

**Last Updated**: February 4, 2026  
**Version**: 1.0.0  
**Status**: Production Ready  
