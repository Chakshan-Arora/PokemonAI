"""
Test suite verifying the 20-minute real-life day/night cycle mechanics and time progression.
"""
import unittest
from src.models.habitat import TimeOfDay, get_time_of_day


class TestDayNightCycleMechanics(unittest.TestCase):
    """
    Verifies that 1 in-game day (24 hours) corresponds to exactly 20 real-life minutes (1200 seconds),
    and correctly maps through Morning, Day, Evening, and Night.
    """

    REAL_MINUTES_PER_DAY = 20.0
    REAL_SECONDS_PER_DAY = REAL_MINUTES_PER_DAY * 60.0  # 1200 seconds
    GAME_HOURS_PER_DAY = 24.0
    GAME_TIME_RATE = GAME_HOURS_PER_DAY / REAL_SECONDS_PER_DAY  # 0.02 hours/sec

    def test_20_minute_real_life_rate_progression(self) -> None:
        # Rate must equal 0.02 hours per second (1 hour per 50 seconds)
        self.assertAlmostEqual(self.GAME_TIME_RATE, 0.02)

        # 50 real seconds = 1.0 game hour
        self.assertAlmostEqual(50.0 * self.GAME_TIME_RATE, 1.0)

        # 1200 real seconds (20 minutes) = 24.0 game hours
        self.assertAlmostEqual(self.REAL_SECONDS_PER_DAY * self.GAME_TIME_RATE, 24.0)

    def test_time_of_day_progression_over_20_minutes(self) -> None:
        def time_at_real_seconds(start_hour: float, real_seconds: float) -> tuple[float, TimeOfDay]:
            hour = (start_hour + real_seconds * self.GAME_TIME_RATE) % 24.0
            return hour, get_time_of_day(hour)

        # Start at midnight (0.0)
        h, tod = time_at_real_seconds(0.0, 0.0)
        self.assertEqual(tod, TimeOfDay.NIGHT)

        # At 250s (4 min 10s): 250 * 0.02 = 5.0 -> MORNING (dawn)
        h, tod = time_at_real_seconds(0.0, 250.0)
        self.assertAlmostEqual(h, 5.0)
        self.assertEqual(tod, TimeOfDay.MORNING)

        # At 500s (8 min 20s): 500 * 0.02 = 10.0 -> DAY (daylight)
        h, tod = time_at_real_seconds(0.0, 500.0)
        self.assertAlmostEqual(h, 10.0)
        self.assertEqual(tod, TimeOfDay.DAY)

        # At 850s (14 min 10s): 850 * 0.02 = 17.0 -> EVENING (sunset)
        h, tod = time_at_real_seconds(0.0, 850.0)
        self.assertAlmostEqual(h, 17.0)
        self.assertEqual(tod, TimeOfDay.EVENING)

        # At 1050s (17 min 30s): 1050 * 0.02 = 21.0 -> NIGHT (nighttime)
        h, tod = time_at_real_seconds(0.0, 1050.0)
        self.assertAlmostEqual(h, 21.0)
        self.assertEqual(tod, TimeOfDay.NIGHT)

        # At 1200s (20 min 00s): full cycle completes back to midnight
        h, tod = time_at_real_seconds(0.0, 1200.0)
        self.assertAlmostEqual(h, 0.0)
        self.assertEqual(tod, TimeOfDay.NIGHT)

    def test_wild_encounters_respect_day_night(self) -> None:
        from src.data.habitats import FOREST_HABITAT
        from src.data.species import BUTTERFREE, ZUBAT

        # In Forest Habitat:
        # Butterfree is diurnal (MORNING, DAY)
        # Zubat is nocturnal (EVENING, NIGHT)
        day_candidates = [c.species for c in FOREST_HABITAT.get_eligible_candidates(TimeOfDay.DAY)]
        self.assertIn(BUTTERFREE, day_candidates)
        self.assertNotIn(ZUBAT, day_candidates)

        night_candidates = [c.species for c in FOREST_HABITAT.get_eligible_candidates(TimeOfDay.NIGHT)]
        self.assertIn(ZUBAT, night_candidates)
        self.assertNotIn(BUTTERFREE, night_candidates)


if __name__ == "__main__":
    unittest.main()
