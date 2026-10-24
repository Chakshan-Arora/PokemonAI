"""
Unit tests for the Pokemon progression and leveling system.

Tests verify:
- XP threshold calculations (formula: current_level * 100).
- XP accumulation without a level-up.
- Single level-up with exact threshold and with remainder.
- Multiple level-ups from a single XP award with carry-over.
- Maximum level (100) capping and XP handling at max level.
- Rejection of invalid XP inputs (negative values, booleans, non-integers).
- Maximum HP recalculation: base_hp + (level * 2).
- Current HP scaling on level-up (benefits from max HP growth, clamps within bounds).
- Preservation of fainted state (0 HP) upon level-up.
- Level bounds (1 to 100) on Pokemon model.
"""
import unittest

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.species import PokemonSpecies
from src.models.pokemon_type import PokemonType
from src.models.progression import (
    MAX_LEVEL,
    XP_PER_LEVEL_MULTIPLIER,
    LevelUpResult,
    get_xp_for_next_level,
    calculate_xp_for_next_level,
    apply_experience,
)
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE


class TestPokemonProgression(unittest.TestCase):
    """Test suite covering progression, leveling math, and HP adjustments."""

    def setUp(self) -> None:
        self.personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )
        self.pikachu = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=5,
            experience=0,
        )

    # --- XP Threshold Calculation ---

    def test_xp_threshold_calculation(self) -> None:
        """Verify XP required for next level follows current_level * 100."""
        self.assertEqual(get_xp_for_next_level(1), 100)
        self.assertEqual(get_xp_for_next_level(2), 200)
        self.assertEqual(get_xp_for_next_level(5), 500)
        self.assertEqual(get_xp_for_next_level(50), 5000)
        self.assertEqual(get_xp_for_next_level(99), 9900)
        self.assertEqual(calculate_xp_for_next_level(5), 500)

        # Invalid level arguments
        with self.assertRaises(ValueError):
            get_xp_for_next_level(0)
        with self.assertRaises(ValueError):
            get_xp_for_next_level(-5)
        with self.assertRaises(ValueError):
            get_xp_for_next_level(101)
        with self.assertRaises(TypeError):
            get_xp_for_next_level("5")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            get_xp_for_next_level(True)  # type: ignore[arg-type]

    # --- XP Accumulation Without Level-Up ---

    def test_xp_accumulation_without_level_up(self) -> None:
        """XP increases towards threshold without incrementing level."""
        # Level 5 requires 500 XP to reach Level 6
        result = apply_experience(self.pikachu, 200)

        self.assertEqual(result.levels_gained, 0)
        self.assertEqual(result.initial_level, 5)
        self.assertEqual(result.final_level, 5)
        self.assertEqual(result.initial_xp, 0)
        self.assertEqual(result.final_xp, 200)
        self.assertEqual(self.pikachu.level, 5)
        self.assertEqual(self.pikachu.experience, 200)
        self.assertEqual(result.hp_gained, 0)

        # Award another 150 XP (total 350 < 500)
        result2 = apply_experience(self.pikachu, 150)
        self.assertEqual(result2.levels_gained, 0)
        self.assertEqual(self.pikachu.level, 5)
        self.assertEqual(self.pikachu.experience, 350)

    # --- Single Level-Up ---

    def test_single_level_up_exact_threshold(self) -> None:
        """Gaining exactly required XP advances level with 0 leftover XP."""
        result = apply_experience(self.pikachu, 500)

        self.assertEqual(result.levels_gained, 1)
        self.assertEqual(result.initial_level, 5)
        self.assertEqual(result.final_level, 6)
        self.assertEqual(result.final_xp, 0)
        self.assertEqual(self.pikachu.level, 6)
        self.assertEqual(self.pikachu.experience, 0)

    def test_single_level_up_with_carryover(self) -> None:
        """XP remaining above threshold carries forward to next level."""
        # 500 needed, 650 awarded -> Level 6 with 150 XP towards Level 7 (needs 600)
        result = apply_experience(self.pikachu, 650)

        self.assertEqual(result.levels_gained, 1)
        self.assertEqual(result.final_level, 6)
        self.assertEqual(result.final_xp, 150)
        self.assertEqual(self.pikachu.level, 6)
        self.assertEqual(self.pikachu.experience, 150)
        self.assertEqual(self.pikachu.xp_for_next_level, 600)

    # --- Multiple Level-Ups ---

    def test_multiple_level_ups_from_single_xp_award(self) -> None:
        """Large XP award triggers multiple sequential level-ups correctly."""
        # Starts at level 5 with 0 XP.
        # Lv 5 -> 6: needs 500 XP (sum: 500)
        # Lv 6 -> 7: needs 600 XP (sum: 1100)
        # Lv 7 -> 8: needs 700 XP (sum: 1800)
        # Award 2000 XP:
        # 2000 - 1800 = 200 XP remaining at Level 8 (which needs 800 XP for Level 9)
        result = apply_experience(self.pikachu, 2000)

        self.assertEqual(result.levels_gained, 3)
        self.assertEqual(result.initial_level, 5)
        self.assertEqual(result.final_level, 8)
        self.assertEqual(result.final_xp, 200)
        self.assertEqual(self.pikachu.level, 8)
        self.assertEqual(self.pikachu.experience, 200)
        self.assertEqual(self.pikachu.xp_for_next_level, 800)

    # --- Maximum Level (100) Handling ---

    def test_maximum_level_capping(self) -> None:
        """Pokemon cannot exceed MAX_LEVEL (100); excess XP is clamped."""
        mon_lvl_99 = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=99,
            experience=0,
        )
        # Lv 99 needs 9900 XP for Lv 100
        # Award 15,000 XP -> reaches 100, no further leveling
        result = apply_experience(mon_lvl_99, 15000)

        self.assertEqual(result.levels_gained, 1)
        self.assertEqual(result.final_level, 100)
        self.assertEqual(mon_lvl_99.level, 100)
        self.assertEqual(mon_lvl_99.experience, 0)
        self.assertTrue(mon_lvl_99.is_max_level)

        # Further XP awarded to level 100 Pokemon produces 0 level-ups
        result_at_max = apply_experience(mon_lvl_99, 5000)
        self.assertEqual(result_at_max.levels_gained, 0)
        self.assertEqual(result_at_max.final_level, 100)
        self.assertEqual(mon_lvl_99.level, 100)

    def test_level_bounds_validation(self) -> None:
        """Level property validates lower bound (1) and upper bound (100)."""
        mon = Pokemon(species=CHARMANDER, personality=self.personality, level=1)
        with self.assertRaises(ValueError):
            mon.level = 0
        with self.assertRaises(ValueError):
            mon.level = -1
        with self.assertRaises(ValueError):
            mon.level = 101

        # Setting valid boundary levels succeeds
        mon.level = 100
        self.assertEqual(mon.level, 100)
        mon.level = 1
        self.assertEqual(mon.level, 1)

    # --- Input Validation ---

    def test_invalid_xp_inputs_rejected(self) -> None:
        """Negative XP and invalid types are rejected with ValueError / TypeError."""
        with self.assertRaises(ValueError):
            apply_experience(self.pikachu, -50)
        with self.assertRaises(TypeError):
            apply_experience(self.pikachu, "100")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            apply_experience(self.pikachu, True)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            apply_experience(self.pikachu, 12.5)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            apply_experience("NotAPokemon", 100)  # type: ignore[arg-type]

    # --- Level-Up Effects on HP ---

    def test_max_hp_recalculated_on_level_up(self) -> None:
        """Max HP adheres strictly to formula: base_hp + (level * 2)."""
        # Pikachu base HP = 11. At level 5: 11 + (5 * 2) = 21.
        self.assertEqual(self.pikachu.max_hp, 21)

        # Level up to 6: 11 + (6 * 2) = 23 (+2 HP)
        apply_experience(self.pikachu, 500)
        self.assertEqual(self.pikachu.level, 6)
        self.assertEqual(self.pikachu.max_hp, 23)

        # Level up to 8 (+2 more levels): 11 + (8 * 2) = 27 (+4 HP)
        apply_experience(self.pikachu, 600 + 700)
        self.assertEqual(self.pikachu.level, 8)
        self.assertEqual(self.pikachu.max_hp, 27)

    def test_current_hp_benefits_from_level_up(self) -> None:
        """When alive, current HP increases by the gained max HP."""
        # Pikachu max HP at level 5 is 21. Take 10 damage -> 11 HP remaining.
        self.pikachu.take_damage(10)
        self.assertEqual(self.pikachu.current_hp, 11)

        # Level up to 6: max HP grows from 21 to 23 (+2).
        # Current HP should become 11 + 2 = 13.
        result = apply_experience(self.pikachu, 500)
        self.assertEqual(result.hp_gained, 2)
        self.assertEqual(self.pikachu.max_hp, 23)
        self.assertEqual(self.pikachu.current_hp, 13)
        self.assertLessEqual(self.pikachu.current_hp, self.pikachu.max_hp)

    def test_fainted_pokemon_hp_remains_zero_on_level_up(self) -> None:
        """A fainted Pokemon retains 0 HP upon level up to preserve fainted invariant."""
        self.pikachu.take_damage(self.pikachu.max_hp)
        self.assertTrue(self.pikachu.is_fainted)
        self.assertEqual(self.pikachu.current_hp, 0)

        # Level up fainted Pokemon
        result = apply_experience(self.pikachu, 500)
        self.assertEqual(result.levels_gained, 1)
        self.assertEqual(self.pikachu.level, 6)
        self.assertEqual(self.pikachu.max_hp, 23)
        self.assertEqual(self.pikachu.current_hp, 0)
        self.assertTrue(self.pikachu.is_fainted)

    def test_pokemon_gain_experience_method(self) -> None:
        """Pokemon.gain_experience delegates cleanly to progression system."""
        result = self.pikachu.gain_experience(500)
        self.assertIsInstance(result, LevelUpResult)
        self.assertEqual(result.levels_gained, 1)
        self.assertEqual(self.pikachu.level, 6)


if __name__ == "__main__":
    unittest.main()
