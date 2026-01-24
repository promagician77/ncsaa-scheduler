"""
Test script for the NCSAA Basketball Scheduling System.
Runs basic tests to verify the system is working correctly.
"""

import sys
import os
from datetime import date, time

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Team, School, Facility, Division, Tier, Cluster, TimeSlot, Game, Schedule
from app.services.validator import ScheduleValidator


def test_models():
    """Test that data models work correctly."""
    print("Testing data models...")
    
    # Create test school
    school = School(name="Test School", cluster=Cluster.EAST, tier=Tier.TIER_1)
    assert school.name == "Test School"
    
    # Create test team
    team = Team(
        id="TEST_001",
        school=school,
        division=Division.ES_BOYS_COMP,
        coach_name="John Doe",
        coach_email="john@test.com"
    )
    assert team.id == "TEST_001"
    assert team.school == school
    
    # Create test facility
    facility = Facility(
        name="Test Gym",
        address="123 Test St",
        max_courts=2
    )
    assert facility.name == "Test Gym"
    assert facility.is_available(date.today())
    
    print("[PASS] Data models test passed")


def test_time_slot():
    """Test time slot functionality."""
    print("Testing time slots...")
    
    facility = Facility(name="Test Gym", address="123 Test St")
    
    slot1 = TimeSlot(
        date=date(2026, 1, 15),
        start_time=time(17, 0),
        end_time=time(18, 0),
        facility=facility,
        court_number=1
    )
    
    slot2 = TimeSlot(
        date=date(2026, 1, 15),
        start_time=time(17, 30),
        end_time=time(18, 30),
        facility=facility,
        court_number=1
    )
    
    # These should overlap
    assert slot1.overlaps_with(slot2)
    
    # Different court, should not overlap
    slot3 = TimeSlot(
        date=date(2026, 1, 15),
        start_time=time(17, 0),
        end_time=time(18, 0),
        facility=facility,
        court_number=2
    )
    assert not slot1.overlaps_with(slot3)
    
    print("[PASS] Time slot test passed")


def test_schedule():
    """Test schedule functionality."""
    print("Testing schedule...")
    
    # Create test data
    school1 = School(name="School A")
    school2 = School(name="School B")
    
    team1 = Team(
        id="TEAM_A",
        school=school1,
        division=Division.ES_BOYS_COMP,
        coach_name="Coach A",
        coach_email="a@test.com"
    )
    
    team2 = Team(
        id="TEAM_B",
        school=school2,
        division=Division.ES_BOYS_COMP,
        coach_name="Coach B",
        coach_email="b@test.com"
    )
    
    facility = Facility(name="Test Gym", address="123 Test St")
    
    slot = TimeSlot(
        date=date(2026, 1, 15),
        start_time=time(17, 0),
        end_time=time(18, 0),
        facility=facility
    )
    
    game = Game(
        id="GAME_001",
        home_team=team1,
        away_team=team2,
        time_slot=slot,
        division=Division.ES_BOYS_COMP
    )
    
    schedule = Schedule(
        season_start=date(2026, 1, 5),
        season_end=date(2026, 2, 28)
    )
    
    schedule.add_game(game)
    
    assert len(schedule.games) == 1
    assert len(schedule.get_team_games(team1)) == 1
    assert len(schedule.get_team_games(team2)) == 1
    assert game.is_home_game(team1)
    assert not game.is_home_game(team2)
    
    print("[PASS] Schedule test passed")


def test_validator():
    """Test schedule validator."""
    print("Testing validator...")
    
    validator = ScheduleValidator()
    
    # Create a simple valid schedule
    school = School(name="Test School")
    team1 = Team(id="T1", school=school, division=Division.ES_BOYS_COMP, coach_name="C1", coach_email="c1@test.com")
    team2 = Team(id="T2", school=school, division=Division.ES_BOYS_COMP, coach_name="C2", coach_email="c2@test.com")
    
    facility = Facility(name="Gym", address="123 St")
    slot = TimeSlot(date=date(2026, 1, 15), start_time=time(17, 0), end_time=time(18, 0), facility=facility)
    
    game = Game(id="G1", home_team=team1, away_team=team2, time_slot=slot, division=Division.ES_BOYS_COMP)
    
    schedule = Schedule(season_start=date(2026, 1, 5), season_end=date(2026, 2, 28))
    schedule.add_game(game)
    
    result = validator.validate_schedule(schedule)
    
    # Should be valid (no hard constraint violations)
    assert result.is_valid
    
    print("[PASS] Validator test passed")


def test_do_not_play():
    """Test do-not-play constraint."""
    print("Testing do-not-play constraint...")
    
    school = School(name="Test School")
    team1 = Team(id="T1", school=school, division=Division.ES_BOYS_COMP, coach_name="C1", coach_email="c1@test.com")
    team2 = Team(id="T2", school=school, division=Division.ES_BOYS_COMP, coach_name="C2", coach_email="c2@test.com")
    
    # Add do-not-play relationship
    team1.do_not_play.add("T2")
    
    facility = Facility(name="Gym", address="123 St")
    slot = TimeSlot(date=date(2026, 1, 15), start_time=time(17, 0), end_time=time(18, 0), facility=facility)
    
    game = Game(id="G1", home_team=team1, away_team=team2, time_slot=slot, division=Division.ES_BOYS_COMP)
    
    schedule = Schedule(season_start=date(2026, 1, 5), season_end=date(2026, 2, 28))
    schedule.add_game(game)
    
    validator = ScheduleValidator()
    result = validator.validate_schedule(schedule)
    
    # Should have a do-not-play violation
    assert not result.is_valid
    assert len(result.hard_constraint_violations) > 0
    assert any(v.constraint_type == "do_not_play_violation" for v in result.hard_constraint_violations)
    
    print("[PASS] Do-not-play constraint test passed")


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Running NCSAA Scheduling System Tests")
    print("=" * 60 + "\n")
    
    try:
        test_models()
        test_time_slot()
        test_schedule()
        test_validator()
        test_do_not_play()
        
        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60 + "\n")
        return 0
        
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
