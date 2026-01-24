# CRITICAL SCHEDULER REDESIGN NEEDED

## Problem Identified

The current scheduler has a **fundamental architectural flaw** that violates the most important rule:

**Rule #15**: "Schools should be clustered together by the school name then the coach. (We have many coaches that coach multiple divisions in a day). **This is the most important thing.**"

### Current (Wrong) Approach
```
For each division:
    Schedule all games for that division
```

This results in:
- Monday: All ES Boys Comp games
- Tuesday: All ES Girls Comp games
- Wednesday: All MS Boys JV games
- etc.

### Required (Correct) Approach
```
For each school matchup (School A vs School B):
    Schedule ALL divisions for these two schools on the same night
    (ES Boys Comp, ES Girls Comp, MS Boys JV, etc.)
```

This results in:
- Monday 5:00 PM: Skye Canyon vs Somerset Sky Pointe
  - Court 1: ES Boys Comp - Skye Canyon (Coach A) vs Somerset Sky Pointe (Coach B)
  - Court 2: ES Girls Comp - Skye Canyon (Coach C) vs Somerset Sky Pointe (Coach D)
  - Court 3: MS Boys JV - Skye Canyon (Coach E) vs Somerset Sky Pointe (Coach F)
  
- Monday 6:00 PM: (Next school matchup)
  - etc.

## Why This Matters

1. **Coaches coach multiple divisions** - they need their teams playing back-to-back
2. **Schools travel together** - all teams from a school should play at the same location
3. **Efficiency** - Parents/fans can watch multiple games from their school
4. **Logistics** - Schools coordinate transportation for all their teams

## Required Changes

### 1. New Scheduling Algorithm Structure

```python
def optimize_schedule_by_schools(self):
    """
    NEW APPROACH: Schedule by school matchups, not by divisions
    """
    # Step 1: Identify all unique schools
    schools = self._get_all_schools()
    
    # Step 2: Create school matchups (School A vs School B)
    school_matchups = self._generate_school_matchups(schools)
    
    # Step 3: For each school matchup, find all division games
    for school_a, school_b in school_matchups:
        # Find all teams from school_a and school_b across ALL divisions
        school_a_teams = self._get_teams_by_school(school_a)
        school_b_teams = self._get_teams_by_school(school_b)
        
        # Create games for each division where both schools have teams
        games_for_this_matchup = []
        for division in DIVISIONS:
            team_a = school_a_teams.get(division)
            team_b = school_b_teams.get(division)
            if team_a and team_b:
                games_for_this_matchup.append(Game(team_a, team_b, division))
        
        # Step 4: Find a time block that can fit all these games
        time_block = self._find_available_time_block(games_for_this_matchup)
        
        # Step 5: Assign consecutive courts/times for this school matchup
        self._assign_time_block(games_for_this_matchup, time_block)
```

### 2. Time Block Concept

A "time block" is a set of consecutive time slots at the same facility:
- **Facility**: Supreme Courtz
- **Date**: Monday, January 6, 2026
- **Time**: 5:00 PM - 8:00 PM
- **Courts**: Courts 1, 2, 3

This allows:
- 5:00 PM: 3 games (one per court)
- 6:00 PM: 3 games (one per court)
- 7:00 PM: 3 games (one per court)

### 3. Coach Clustering

Within a school matchup, games should be ordered by coach:
- If Coach Smith coaches ES Boys Comp AND MS Boys JV, schedule those back-to-back
- This allows the coach to be at both games

### 4. Special Cases

#### Rec Divisions (Rule #8, #9)
- ES K-1 REC and ES 2-3 REC must be grouped together
- ES K-1 REC needs 8ft rims (specific facilities)
- These should be first or last games of the day

#### Schools with Multiple Teams in Same Division (Rule #23)
- Already fixed: these teams never play each other
- But they can play on the same night against different opponents

## Implementation Priority

1. **CRITICAL**: Redesign core scheduling algorithm to group by schools
2. **HIGH**: Implement time block allocation
3. **HIGH**: Implement coach clustering within school matchups
4. **MEDIUM**: Handle special cases (Rec divisions, 8ft rims)
5. **MEDIUM**: Optimize for tier/cluster matching within school matchups

## Testing

After redesign, verify:
1. ✅ All teams from School A play on same night
2. ✅ All teams from School A play against School B on same night
3. ✅ Games are in consecutive time slots (back-to-back)
4. ✅ Coaches with multiple teams have back-to-back games
5. ✅ No same-school matchups (Rule #23)
6. ✅ All teams play exactly 8 games (Rule #22)
7. ✅ Rec divisions are grouped (Rule #8)

## Estimated Effort

This is a **major rewrite** of the core scheduling algorithm. The current division-based approach cannot be patched - it needs to be completely replaced with a school-based approach.

**Estimated time**: 3-4 hours for complete redesign and testing
