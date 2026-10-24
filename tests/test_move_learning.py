"""
Unit tests for level-up move learning progression and integration.
"""
import unittest

from src.models.pokemon import Pokemon, MAX_KNOWN_MOVES
from src.models.personality import Personality
from src.models.progression import apply_experience, LevelUpResult
from src.models.species import PokemonSpecies
from src.models.pokemon_type import PokemonType
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import (
    TACKLE,
    QUICK_ATTACK,
    SCRATCH,
    THUNDER_SHOCK,
    THUNDERBOLT,
    EMBER,
    FLAMETHROWER,
    WATER_GUN,
    HYDRO_PUMP,
)
from src.data.move_learning import (
    LevelUpMove,
    SPECIES_MOVE_LEARNING,
    get_learnable_moves,
    get_moves_at_level,
    get_moves_in_level_range,
)
from src.models.move_manager import (
    MoveManager,
    PendingMove,
    LevelUpMoveProgressionResult,
)


class TestMoveLearning(unittest.TestCase):
    """Test suite for data-driven move learning and progression integration."""

    def setUp(self) -> None:
        self.move_manager = MoveManager()
        self.personality = Personality(aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50)

    def _create_pokemon(self, species=PIKACHU, level=1, attacks=None) -> Pokemon:
        return Pokemon(
            species=species,
            level=level,
            personality=self.personality,
            attacks=attacks if attacks is not None else [],
        )

    def test_01_species_move_tables_are_defined_and_valid(self) -> None:
        """Move tables exist for Pikachu, Charmander, and Squirtle with valid LevelUpMove entries."""
        for species_name in ("Pikachu", "Charmander", "Squirtle"):
            moves = get_learnable_moves(species_name)
            self.assertTrue(len(moves) >= 4)
            levels = [m.level for m in moves]
            self.assertEqual(levels, sorted(levels), f"Moves for {species_name} should be sorted by level.")
            for m in moves:
                self.assertIsInstance(m, LevelUpMove)
                self.assertGreaterEqual(m.level, 1)
                self.assertIsNotNone(m.attack.name)

    def test_02_query_moves_at_level(self) -> None:
        """get_moves_at_level returns attacks configured for that specific level."""
        pika_lv1 = get_moves_at_level(PIKACHU, 1)
        self.assertEqual(len(pika_lv1), 1)
        self.assertIs(pika_lv1[0], THUNDER_SHOCK)

        pika_lv3 = get_moves_at_level(PIKACHU, 3)
        self.assertEqual(len(pika_lv3), 1)
        self.assertIs(pika_lv3[0], QUICK_ATTACK)

        pika_lv5 = get_moves_at_level(PIKACHU, 5)
        self.assertEqual(pika_lv5, ())

    def test_03_query_moves_in_level_range(self) -> None:
        """get_moves_in_level_range extracts moves in ascending order."""
        # Range 1 to 6 (exclusive of start, inclusive of end)
        moves = get_moves_in_level_range(PIKACHU, start_level=1, end_level=6)
        # Should include Lv.3 Quick Attack, Lv.6 Tackle
        self.assertEqual(len(moves), 2)
        self.assertEqual(moves[0].attack.name, "Quick Attack")
        self.assertEqual(moves[1].attack.name, "Tackle")

    def test_04_moves_not_learned_before_reaching_level(self) -> None:
        """Advancing to a level prior to a move threshold learns nothing."""
        pika = self._create_pokemon(species=PIKACHU, level=1, attacks=[THUNDER_SHOCK])
        result = self.move_manager.process_level_up_moves(pika, from_level=1, to_level=2)

        self.assertEqual(len(result.learned_moves), 0)
        self.assertEqual(len(result.pending_moves), 0)
        self.assertEqual(len(pika.attacks), 1)

    def test_05_single_level_up_threshold_learned(self) -> None:
        """Advancing from level 2 to 3 teaches Pikachu Quick Attack."""
        pika = self._create_pokemon(species=PIKACHU, level=2, attacks=[THUNDER_SHOCK])
        result = self.move_manager.process_level_up_moves(pika, from_level=2, to_level=3)

        self.assertEqual(len(result.learned_moves), 1)
        self.assertIs(result.learned_moves[0], QUICK_ATTACK)
        self.assertIn(QUICK_ATTACK, pika.attacks)
        self.assertEqual(len(pika.attacks), 2)

    def test_06_multi_level_progression_in_ascending_order(self) -> None:
        """Jumping multiple levels processes and learns moves in strict ascending level order."""
        charm = self._create_pokemon(species=CHARMANDER, level=1, attacks=[SCRATCH])
        # Level 1 to 7 crosses Lv.3 (Ember) and Lv.6 (Tackle)
        result = self.move_manager.process_level_up_moves(charm, from_level=1, to_level=7)

        self.assertEqual(len(result.learned_moves), 2)
        self.assertEqual(result.learned_moves[0], EMBER)
        self.assertEqual(result.learned_moves[1], TACKLE)
        self.assertEqual(charm.attacks, [SCRATCH, EMBER, TACKLE])

    def test_07_no_repeated_moves_for_same_level(self) -> None:
        """Re-running move progression across the same level range does not duplicate moves."""
        pika = self._create_pokemon(species=PIKACHU, level=1, attacks=[THUNDER_SHOCK])

        res1 = self.move_manager.process_level_up_moves(pika, from_level=1, to_level=3)
        self.assertEqual(len(res1.learned_moves), 1)

        # Call again for the same transition
        res2 = self.move_manager.process_level_up_moves(pika, from_level=1, to_level=3)
        self.assertEqual(len(res2.learned_moves), 0)
        self.assertEqual(len(pika.attacks), 2)

    def test_08_moves_already_known_are_skipped_cleanly(self) -> None:
        """If a Pokemon already knows a move via prior learning, it is recorded in skipped_moves."""
        pika = self._create_pokemon(species=PIKACHU, level=1, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        result = self.move_manager.process_level_up_moves(pika, from_level=1, to_level=3)

        self.assertEqual(len(result.learned_moves), 0)
        self.assertEqual(len(result.skipped_moves), 1)
        self.assertIs(result.skipped_moves[0], QUICK_ATTACK)
        self.assertEqual(len(pika.attacks), 2)

    def test_09_four_move_limit_creates_pending_move_without_overwriting(self) -> None:
        """When 4 moves are already known, eligible level-up moves become PendingMove objects."""
        # Give Squirtle 4 custom attacks
        squirtle = self._create_pokemon(
            species=SQUIRTLE,
            level=1,
            attacks=[TACKLE, WATER_GUN, QUICK_ATTACK, EMBER],
        )
        self.assertEqual(len(squirtle.attacks), 4)

        # Advance to Lv.10 where Hydro Pump is learned
        result = self.move_manager.process_level_up_moves(squirtle, from_level=1, to_level=10)

        self.assertEqual(len(result.learned_moves), 0)
        self.assertEqual(len(result.pending_moves), 1)
        pending = result.pending_moves[0]
        self.assertIs(pending.attack, HYDRO_PUMP)
        self.assertEqual(pending.level, 10)
        self.assertIn("move replacement decision is required", pending.reason.lower(), msg=pending.reason)

        # Existing 4 moves are completely untouched
        self.assertEqual(squirtle.attacks, [TACKLE, WATER_GUN, QUICK_ATTACK, EMBER])

        # Trainer can now explicitly replace a move using the pending move
        replace_res = self.move_manager.replace_attack(squirtle, EMBER, pending.attack)
        self.assertTrue(replace_res.success)
        self.assertIn(HYDRO_PUMP, squirtle.attacks)
        self.assertNotIn(EMBER, squirtle.attacks)
        self.assertEqual(len(squirtle.attacks), 4)

    def test_10_unknown_species_handled_gracefully(self) -> None:
        """Species without a move-learning table yield empty results without crashing."""
        unknown_species = PokemonSpecies(
            name="MysteryMon",
            primary_type=PokemonType.NORMAL,
            base_hp=40,
            base_attack=50,
            base_defense=40,
            base_speed=50,
        )
        mystery = self._create_pokemon(species=unknown_species, level=1)
        result = self.move_manager.process_level_up_moves(mystery, from_level=1, to_level=20)

        self.assertEqual(len(result.learned_moves), 0)
        self.assertEqual(len(result.pending_moves), 0)
        self.assertEqual(len(result.skipped_moves), 0)

    def test_11_progression_hp_stability_and_integration(self) -> None:
        """Leveling up via progression manager, gaining HP, and checking moves works seamlessly."""
        pika = self._create_pokemon(species=PIKACHU, level=1, attacks=[THUNDER_SHOCK])
        initial_hp = pika.current_hp
        initial_max_hp = pika.max_hp

        # Award enough XP to reach Level 3 (Lv.1 requires 100 XP, Lv.2 requires 200 XP -> 300 XP total)
        level_result = apply_experience(pika, 300)
        self.assertEqual(pika.level, 3)
        self.assertEqual(pika.max_hp, initial_max_hp + 4)
        self.assertEqual(pika.current_hp, initial_hp + 4)

        # Use coordinator check_level_up_moves
        move_result = self.move_manager.check_level_up_moves(level_result)
        self.assertEqual(len(move_result.learned_moves), 1)
        self.assertIs(move_result.learned_moves[0], QUICK_ATTACK)
        self.assertIn(QUICK_ATTACK, pika.attacks)

        # Ensure HP invariants remain intact
        self.assertGreater(pika.current_hp, 0)
        self.assertEqual(pika.current_hp, pika.max_hp)

    def test_12_invalid_level_ranges_handled_safely(self) -> None:
        """Decreasing or non-integer level ranges return clean empty progression results."""
        pika = self._create_pokemon(species=PIKACHU, level=5)
        # to_level <= from_level
        res1 = self.move_manager.process_level_up_moves(pika, from_level=5, to_level=5)
        self.assertEqual(len(res1.learned_moves), 0)

        res2 = self.move_manager.process_level_up_moves(pika, from_level=5, to_level=2)
        self.assertEqual(len(res2.learned_moves), 0)

        with self.assertRaises(TypeError):
            self.move_manager.process_level_up_moves(pika, "1", 5)  # type: ignore

        with self.assertRaises(TypeError):
            self.move_manager.process_level_up_moves(pika, 1, "5")  # type: ignore


if __name__ == "__main__":
    unittest.main()
