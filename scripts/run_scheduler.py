"""
Main entry point for the NCSAA Basketball Scheduling System (CLI).
Orchestrates the complete scheduling workflow.
"""

import sys
import argparse
from datetime import datetime
import os

# Add backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sheets_reader import SheetsReader
from app.services.scheduler_v2 import SchoolBasedScheduler
from app.services.validator import ScheduleValidator


def main():
    """
    Main function to run the scheduling system.
    Coordinates data loading, schedule optimization, validation, and output.
    """
    parser = argparse.ArgumentParser(
        description='NCSAA Basketball Scheduling System - Generate optimized game schedules'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate existing schedule without generating new one'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("NCSAA BASKETBALL SCHEDULING SYSTEM")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        # Step 1: Load data from Google Sheets
        print("\n[STEP 1] Loading data from Google Sheets...")
        reader = SheetsReader()
        teams, facilities, rules = reader.load_all_data()
        
        if not teams:
            print("ERROR: No teams loaded. Please check the Google Sheet.")
            return 1
        
        if not facilities:
            print("ERROR: No facilities loaded. Please check the Google Sheet.")
            return 1
        
        print(f"\nLoaded:")
        print(f"  - {len(teams)} teams")
        print(f"  - {len(facilities)} facilities")
        print(f"  - Season: {rules.get('season_start')} to {rules.get('season_end')}")
        
        # Step 2: Generate optimized schedule (using school-based clustering)
        print("\n[STEP 2] Generating optimized schedule...")
        print("Using school-based clustering algorithm (Rule #15)")
        optimizer = SchoolBasedScheduler(teams, facilities, rules)
        schedule = optimizer.optimize_schedule()
        
        if not schedule or len(schedule.games) == 0:
            print("ERROR: Failed to generate schedule.")
            return 1
        
        print(f"\nGenerated schedule with {len(schedule.games)} games")
        
        # Step 3: Validate schedule
        print("\n[STEP 3] Validating schedule...")
        validator = ScheduleValidator()
        validation_result = validator.validate_schedule(schedule)
        
        # Print validation summary
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        print(validation_result.get_summary())
        
        if not validation_result.is_valid:
            print("\nWARNING: Schedule has hard constraint violations!")
            print("The schedule will still be written, but manual adjustments may be needed.")
        
        # Step 4: Generate detailed report
        print("\n[STEP 4] Generating schedule report...")
        report = validator.generate_schedule_report(schedule)
        print("\n" + report)
        
        # Step 5: Schedule generation complete (no longer writing to Google Sheets)
        print("\n[STEP 5] Schedule generation complete")
        print("Schedule is ready for use via API or frontend")
        
        # Final summary
        print("\n" + "=" * 80)
        print("SCHEDULING COMPLETE")
        print("=" * 80)
        print(f"Total games scheduled: {len(schedule.games)}")
        print(f"Schedule valid: {'Yes' if validation_result.is_valid else 'No (with violations)'}")
        print(f"Hard violations: {len(validation_result.hard_constraint_violations)}")
        print(f"Soft violations: {len(validation_result.soft_constraint_violations)}")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nScheduling interrupted by user.")
        return 1
    
    except Exception as e:
        print(f"\n\nERROR: An unexpected error occurred:")
        print(f"{type(e).__name__}: {e}")
        
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        
        return 1


if __name__ == '__main__':
    sys.exit(main())
