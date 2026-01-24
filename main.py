"""
Main entry point for the NCSAA Basketball Scheduling System.
Orchestrates the complete scheduling workflow.
"""

import sys
import argparse
from datetime import datetime

from sheets_reader import SheetsReader
from scheduler import ScheduleOptimizer
from validator import ScheduleValidator
from sheets_writer import SheetsWriter


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
        '--no-write',
        action='store_true',
        help='Generate schedule but do not write to Google Sheets'
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
        
        # Step 2: Generate optimized schedule
        print("\n[STEP 2] Generating optimized schedule...")
        optimizer = ScheduleOptimizer(teams, facilities, rules)
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
        
        # Step 5: Write schedule to Google Sheets
        if not args.no_write:
            print("\n[STEP 5] Writing schedule to Google Sheets...")
            writer = SheetsWriter()
            
            # Write weekly schedules
            writer.write_schedule(schedule)
            
            # Write summary sheet
            writer.write_summary_sheet(schedule, validation_result)
            
            # Write team schedules
            writer.write_team_schedules(schedule)
            
            print("\nSchedule successfully written to Google Sheets!")
            print(f"View at: https://docs.google.com/spreadsheets/d/{reader.spreadsheet.id}")
        else:
            print("\n[STEP 5] Skipping write to Google Sheets (--no-write flag)")
        
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
