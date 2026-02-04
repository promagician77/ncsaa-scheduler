"""
Diagnostic script to check facility availability in the first week.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sheets_reader import SheetsReader
from datetime import date

def main():
    print("=" * 80)
    print("FACILITY AVAILABILITY DIAGNOSTIC")
    print("=" * 80)
    
    reader = SheetsReader()
    teams, facilities, rules = reader.load_all_data()
    
    # Check first week (Jan 5-11, 2026)
    first_week = [
        date(2026, 1, 5),   # Sunday
        date(2026, 1, 6),   # Monday
        date(2026, 1, 7),   # Tuesday
        date(2026, 1, 8),   # Wednesday
        date(2026, 1, 9),   # Thursday
        date(2026, 1, 10),  # Saturday
        date(2026, 1, 11),  # Sunday
    ]
    
    print("\n" + "=" * 80)
    print("FIRST WEEK FACILITY AVAILABILITY (Jan 5-11, 2026)")
    print("=" * 80)
    
    # Focus on Faith and LVBC
    target_facilities = []
    for facility in facilities:
        if 'faith' in facility.name.lower() or 'lvbc' in facility.name.lower() or 'las vegas basketball' in facility.name.lower():
            target_facilities.append(facility)
    
    if not target_facilities:
        print("\n⚠️  No Faith or LVBC facilities found!")
        print("\nAll facilities:")
        for f in facilities[:10]:
            print(f"  - {f.name}")
    else:
        for facility in target_facilities:
            print(f"\n{'='*80}")
            print(f"FACILITY: {facility.name}")
            print(f"{'='*80}")
            print(f"  Max Courts: {facility.max_courts}")
            print(f"  Has 8ft Rims: {facility.has_8ft_rims}")
            print(f"  Total available_dates: {len(facility.available_dates)}")
            
            if facility.available_dates:
                sorted_dates = sorted(facility.available_dates)
                print(f"  First available date: {sorted_dates[0]}")
                print(f"  Last available date: {sorted_dates[-1]}")
                print(f"  First 10 dates: {sorted_dates[:10]}")
            else:
                print("  ⚠️  No available_dates specified (available ALL dates)")
            
            print(f"\n  Unavailable dates: {len(facility.unavailable_dates)}")
            if facility.unavailable_dates:
                print(f"  Unavailable: {sorted(facility.unavailable_dates)[:10]}")
            
            # Check first week availability
            print(f"\n  FIRST WEEK AVAILABILITY:")
            for day in first_week:
                day_name = day.strftime("%A, %b %d")
                is_avail = facility.is_available(day)
                status = "✅ AVAILABLE" if is_avail else "❌ NOT AVAILABLE"
                print(f"    {day_name}: {status}")
                
                # Explain why not available
                if not is_avail:
                    if facility.unavailable_dates and day in facility.unavailable_dates:
                        print(f"      → Reason: In unavailable_dates list")
                    elif facility.available_dates and day not in facility.available_dates:
                        print(f"      → Reason: NOT in available_dates list (has {len(facility.available_dates)} dates)")
    
    # Check all facilities summary
    print("\n" + "=" * 80)
    print("ALL FACILITIES SUMMARY")
    print("=" * 80)
    
    facilities_available_first_week = []
    for facility in facilities:
        # Check if available on Monday Jan 6 (first weekday)
        monday_jan_6 = date(2026, 1, 6)
        if facility.is_available(monday_jan_6) and facility.max_courts > 0:
            facilities_available_first_week.append(facility.name)
    
    print(f"\nFacilities available on Monday, Jan 6, 2026: {len(facilities_available_first_week)}")
    for name in facilities_available_first_week[:15]:
        print(f"  ✅ {name}")
    
    if len(facilities_available_first_week) > 15:
        print(f"  ... and {len(facilities_available_first_week) - 15} more")
    
    # Check blackouts
    print("\n" + "=" * 80)
    print("SCHOOL BLACKOUTS (First Week)")
    print("=" * 80)
    
    blackouts = rules.get('blackouts', {})
    print(f"\nTotal schools with blackouts: {len(blackouts)}")
    
    # Check Faith school blackouts
    for school_name in blackouts:
        if 'faith' in school_name.lower():
            print(f"\n{school_name}:")
            first_week_blackouts = [d for d in blackouts[school_name] if d in first_week]
            if first_week_blackouts:
                print(f"  ⚠️  Blackouts in first week: {first_week_blackouts}")
            else:
                print(f"  ✅ No blackouts in first week")
            print(f"  Total blackouts: {len(blackouts[school_name])}")
            if blackouts[school_name]:
                print(f"  First 10 blackouts: {sorted(blackouts[school_name])[:10]}")

if __name__ == "__main__":
    main()
