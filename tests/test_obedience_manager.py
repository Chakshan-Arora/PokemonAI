"""
Unit tests for Pokemon obedience manager, formula calculations, and deterministic evaluations.
"""
import random
import unittest
from unittest.mock import MagicMock
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.obedience_manager import (
    ObedienceManager,
    ObedienceResult,
    CommandContext,
    calculate_obedience_probability,
    BASE_OBEDIENCE_PROBABILITY,
    OBEDIENCE_WEIGHT,
    BOND_WEIGHT,
    MIN_OBEDIENCE_PROBABILITY,
    MAX_OBEDIENCE_PROBABILITY,
)
from src.data.species import PIKACHU, CHARMANDER


class TestObedienceManager(unittest.TestCase):
    """
    Exhaustive tests verifying obedience probability formula, stat weightings,
    deterministic rolls, edge conditions, and immutability.
    """

    def setUp(self) -> None:
        self.personality = Personality(50, 50, 50, 50, 50, 50)
        self.pika = Pokemon(species=PIKACHU, personality=self.personality, bond=50, obedience=80)
        self.manager = ObedienceManager(seed=42)

    def test_01_probability_formula_expected_values(self) -> None:
        """Exhaustively verifies formula output across known benchmark stat combinations."""
        # Case A: Max obedience (100) and Max bond (100) -> 0.70 + 0.25 + 0.05 = 1.00
        p_max = Pokemon(species=PIKACHU, personality=self.personality, obedience=100, bond=100)
        self.assertAlmostEqual(calculate_obedience_probability(p_max), 1.00, places=5)

        # Case B: Max obedience (100) and Zero bond (0) -> 0.70 + 0.25 + 0.00 = 0.95
        p_lo_bond = Pokemon(species=PIKACHU, personality=self.personality, obedience=100, bond=0)
        self.assertAlmostEqual(calculate_obedience_probability(p_lo_bond), 0.95, places=5)

        # Case C: Zero obedience (0) and Max bond (100) -> 0.70 + 0.00 + 0.05 = 0.75
        p_lo_ob = Pokemon(species=PIKACHU, personality=self.personality, obedience=0, bond=100)
        self.assertAlmostEqual(calculate_obedience_probability(p_lo_ob), 0.75, places=5)

        # Case D: Zero obedience (0) and Zero bond (0) -> 0.70 + 0.00 + 0.00 = 0.70
        p_zero = Pokemon(species=PIKACHU, personality=self.personality, obedience=0, bond=0)
        self.assertAlmostEqual(calculate_obedience_probability(p_zero), 0.70, places=5)

        # Case E: Mid obedience (50) and Mid bond (50) -> 0.70 + 0.125 + 0.025 = 0.85
        p_mid = Pokemon(species=PIKACHU, personality=self.personality, obedience=50, bond=50)
        self.assertAlmostEqual(calculate_obedience_probability(p_mid), 0.85, places=5)

    def test_02_probability_remains_within_documented_bounds(self) -> None:
        """Probability is strictly bounded within [MIN_OBEDIENCE_PROBABILITY, MAX_OBEDIENCE_PROBABILITY]."""
        # Upper bound clamping with large negative difficulty modifier
        easy_ctx = CommandContext(command="easy", difficulty_modifier=-0.50)
        prob_upper = calculate_obedience_probability(self.pika, context=easy_ctx)
        self.assertLessEqual(prob_upper, MAX_OBEDIENCE_PROBABILITY)
        self.assertEqual(prob_upper, 1.00)

        # Lower bound clamping with high difficulty modifier
        hard_ctx = CommandContext(command="hard", difficulty_modifier=0.95)
        prob_lower = calculate_obedience_probability(self.pika, context=hard_ctx)
        self.assertGreaterEqual(prob_lower, MIN_OBEDIENCE_PROBABILITY)
        self.assertEqual(prob_lower, 0.05)

    def test_03_high_obedience_produces_higher_probability_than_low_obedience(self) -> None:
        """Under equivalent bond conditions, higher obedience strictly increases probability."""
        p_high = Pokemon(species=PIKACHU, personality=self.personality, obedience=90, bond=40)
        p_low = Pokemon(species=PIKACHU, personality=self.personality, obedience=20, bond=40)

        prob_high = self.manager.calculate_probability(p_high)
        prob_low = self.manager.calculate_probability(p_low)

        self.assertGreater(prob_high, prob_low)
        # Expected difference: (90 - 20)/100 * 0.25 = 0.70 * 0.25 = 0.175
        self.assertAlmostEqual(prob_high - prob_low, 0.175, places=5)

    def test_04_bond_provides_smaller_influence_than_obedience(self) -> None:
        """Verifies that obedience has 5x the weight of bond on probability."""
        p_base = Pokemon(species=PIKACHU, personality=self.personality, obedience=0, bond=0)
        base_prob = self.manager.calculate_probability(p_base)

        # Add 50 obedience
        p_ob_boost = Pokemon(species=PIKACHU, personality=self.personality, obedience=50, bond=0)
        ob_gain = self.manager.calculate_probability(p_ob_boost) - base_prob

        # Add 50 bond
        p_bond_boost = Pokemon(species=PIKACHU, personality=self.personality, obedience=0, bond=50)
        bond_gain = self.manager.calculate_probability(p_bond_boost) - base_prob

        self.assertAlmostEqual(ob_gain, 0.125, places=5)
        self.assertAlmostEqual(bond_gain, 0.025, places=5)
        self.assertGreater(ob_gain, bond_gain)
        self.assertAlmostEqual(ob_gain / bond_gain, 5.0, places=5)

    def test_05_injected_randomness_makes_tests_deterministic(self) -> None:
        """The same seed produces identical rolls and obedience outcomes."""
        p = Pokemon(species=CHARMANDER, personality=self.personality, obedience=70, bond=60)
        mgr1 = ObedienceManager(seed=999)
        mgr2 = ObedienceManager(seed=999)

        res1 = mgr1.evaluate_obedience(p, "attack")
        res2 = mgr2.evaluate_obedience(p, "attack")

        self.assertEqual(res1.roll, res2.roll)
        self.assertEqual(res1.is_obeyed, res2.is_obeyed)
        self.assertEqual(res1.probability, res2.probability)

    def test_06_commands_succeed_or_fail_at_expected_random_thresholds(self) -> None:
        """Injecting specific RNG values reliably produces obedience or disobedience."""
        # For mid stats, probability is 0.85
        p_mid = Pokemon(species=PIKACHU, personality=self.personality, obedience=50, bond=50)
        prob = self.manager.calculate_probability(p_mid)
        self.assertAlmostEqual(prob, 0.85, places=5)

        # Roll 0.80 <= 0.85 -> Obeyed
        mock_rng_pass = MagicMock()
        mock_rng_pass.random.return_value = 0.80
        res_pass = self.manager.evaluate_obedience(p_mid, "Thunder Shock", rng=mock_rng_pass)
        self.assertTrue(res_pass.is_obeyed)
        self.assertEqual(res_pass.roll, 0.80)
        self.assertIn("obeyed", res_pass.reason)

        # Roll 0.90 > 0.85 -> Disobeyed
        mock_rng_fail = MagicMock()
        mock_rng_fail.random.return_value = 0.90
        res_fail = self.manager.evaluate_obedience(p_mid, "Thunder Shock", rng=mock_rng_fail)
        self.assertFalse(res_fail.is_obeyed)
        self.assertEqual(res_fail.roll, 0.90)
        self.assertIn("ignored", res_fail.reason)

    def test_07_invalid_inputs_handled_safely(self) -> None:
        """Handles non-Pokemon and fainted Pokemon safely."""
        with self.assertRaises(TypeError):
            calculate_obedience_probability("NotAPokemon")  # type: ignore

        # Evaluating non-Pokemon returns structured failure
        res_invalid = self.manager.evaluate_obedience("NotAPokemon")  # type: ignore
        self.assertFalse(res_invalid.is_obeyed)
        self.assertEqual(res_invalid.probability, 0.0)
        self.assertIn("Invalid Pokemon", res_invalid.reason)

        # Fainted Pokemon cannot obey
        self.pika.current_hp = 0
        self.assertTrue(self.pika.is_fainted)
        res_fainted = self.manager.evaluate_obedience(self.pika, "Quick Attack")
        self.assertFalse(res_fainted.is_obeyed)
        self.assertEqual(res_fainted.probability, 0.0)
        self.assertIn("fainted", res_fainted.reason)

    def test_08_evaluation_does_not_mutate_pokemon_state(self) -> None:
        """Evaluating obedience never modifies bond, obedience, level, or HP."""
        initial_bond = self.pika.bond
        initial_obedience = self.pika.obedience
        initial_hp = self.pika.current_hp
        initial_lvl = self.pika.level

        for _ in range(5):
            self.manager.evaluate_obedience(self.pika, "test_cmd")

        self.assertEqual(self.pika.bond, initial_bond)
        self.assertEqual(self.pika.obedience, initial_obedience)
        self.assertEqual(self.pika.current_hp, initial_hp)
        self.assertEqual(self.pika.level, initial_lvl)


if __name__ == "__main__":
    unittest.main()
