import sys
import argparse
from datetime import datetime
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sheets_reader import SheetsReader
from app.services.scheduler import ScheduleOptimizer
from app.services.validator import ScheduleValidator


def main():
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
    
    try:
        reader = SheetsReader()
        teams, facilities, rules = reader.load_all_data()
        
        if not teams:
            print("ERROR: No teams loaded. Please check the Google Sheet.")
            return 1
        
        if not facilities:
            print("ERROR: No facilities loaded. Please check the Google Sheet.")
            return 1
        
        optimizer = ScheduleOptimizer(teams, facilities, rules)
        schedule = optimizer.optimize_schedule()
        
        if not schedule or len(schedule.games) == 0:
            print("ERROR: Failed to generate schedule.")
            return 1
        
        print(f"\nGenerated schedule with {len(schedule.games)} games")
        
        validator = ScheduleValidator()
        validation_result = validator.validate_schedule(schedule)
        
        if not validation_result.is_valid:
            print("\nWARNING: Schedule has hard constraint violations!")
            print("The schedule will still be written, but manual adjustments may be needed.")
        
        print("\n[STEP 4] Generating schedule report...")
        report = validator.generate_schedule_report(schedule)
        print("\n" + report)
        
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
