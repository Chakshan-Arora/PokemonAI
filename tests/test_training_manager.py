"""
Unit tests for Pokemon training manager, individual stat growth, stat caps, and battle integration.
"""
import unittest
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.training_manager import (
    TrainingManager,
    TrainingResult,
    TrainingConfig,
    SUPPORTED_TRAINING_STATS,
    DEFAULT_TRAINING_AMOUNT,
    DEFAULT_STAT_CAP,
)
from src.models.damage_calculator import calculate_damage
from src.models.battle import Battle
from src.models.progression import apply_experience
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, TACKLE, WATER_GUN


class TestTrainingManager(unittest.TestCase):
    """
    Exhaustive tests for TrainingManager, individual stat storage,
    stat caps, clamping, and battle engine integration.
    """

    def setUp(self) -> None:
        self.personality = Personality(50, 50, 50, 50, 50, 50)
        self.pika = Pokemon(species=PIKACHU, personality=self.personality)
        self.squirtle = Pokemon(species=SQUIRTLE, personality=self.personality)
        self.charmander = Pokemon(species=CHARMANDER, personality=self.personality)
        self.manager = TrainingManager()

    def test_01_successful_attack_training(self) -> None:
        """Attack stat increases by default amount on target instance."""
        initial_atk = self.pika.attack
        self.assertEqual(initial_atk, 55)

        res = self.manager.train_attack(self.pika)
        self.assertTrue(res.success)
        self.assertEqual(res.stat_name, "attack")
        self.assertEqual(res.previous_value, 55)
        self.assertEqual(res.new_value, 60)
        self.assertEqual(res.actual_change, DEFAULT_TRAINING_AMOUNT)
        self.assertFalse(res.was_clamped)
        self.assertEqual(self.pika.attack, 60)
        self.assertEqual(self.pika.trained_attack, 5)

    def test_02_successful_defense_training(self) -> None:
        """Defense stat increases by default amount on target instance."""
        initial_def = self.squirtle.defense
        self.assertEqual(initial_def, 65)

        res = self.manager.train_defense(self.squirtle)
        self.assertTrue(res.success)
        self.assertEqual(res.stat_name, "defense")
        self.assertEqual(res.previous_value, 65)
        self.assertEqual(res.new_value, 70)
        self.assertEqual(res.actual_change, 5)
        self.assertEqual(self.squirtle.defense, 70)
        self.assertEqual(self.squirtle.trained_defense, 5)

    def test_03_successful_speed_training(self) -> None:
        """Speed stat increases by default amount on target instance."""
        initial_spd = self.charmander.speed
        self.assertEqual(initial_spd, 65)

        res = self.manager.train_speed(self.charmander)
        self.assertTrue(res.success)
        self.assertEqual(res.stat_name, "speed")
        self.assertEqual(res.previous_value, 65)
        self.assertEqual(res.new_value, 70)
        self.assertEqual(res.actual_change, 5)
        self.assertEqual(self.charmander.speed, 70)
        self.assertEqual(self.charmander.trained_speed, 5)

    def test_04_training_by_custom_amount(self) -> None:
        """Training accepts and correctly applies custom positive integer amount."""
        res = self.manager.train_stat(self.pika, "attack", amount=12)
        self.assertTrue(res.success)
        self.assertEqual(res.previous_value, 55)
        self.assertEqual(res.new_value, 67)
        self.assertEqual(res.actual_change, 12)
        self.assertEqual(self.pika.attack, 67)

    def test_05_stat_cap_enforcement_and_clamping(self) -> None:
        """Clamps stat growth at configured cap and reports actual change."""
        # Configure a custom tight cap of 60 for Attack
        custom_manager = TrainingManager(stat_caps={"attack": 60})
        self.assertEqual(self.pika.attack, 55)

        # 1. Partial clamp: 55 + 10 would be 65, clamped to 60 (actual change +5)
        res_clamp = custom_manager.train_stat(self.pika, "attack", amount=10)
        self.assertTrue(res_clamp.success)
        self.assertEqual(res_clamp.previous_value, 55)
        self.assertEqual(res_clamp.new_value, 60)
        self.assertEqual(res_clamp.actual_change, 5)
        self.assertTrue(res_clamp.was_clamped)
        self.assertEqual(self.pika.attack, 60)

        # 2. Training when already at cap is safely rejected with actual_change 0
        res_full = custom_manager.train_stat(self.pika, "attack", amount=5)
        self.assertFalse(res_full.success)
        self.assertEqual(res_full.previous_value, 60)
        self.assertEqual(res_full.new_value, 60)
        self.assertEqual(res_full.actual_change, 0)
        self.assertTrue(res_full.was_clamped)
        self.assertIn("already at or above maximum cap", res_full.reason)

    def test_06_rejection_of_zero_and_negative_amounts(self) -> None:
        """Zero and negative amounts are rejected cleanly."""
        res_zero = self.manager.train_stat(self.pika, "attack", amount=0)
        self.assertFalse(res_zero.success)
        self.assertEqual(res_zero.actual_change, 0)
        self.assertIn("positive", res_zero.reason)

        res_neg = self.manager.train_stat(self.pika, "attack", amount=-5)
        self.assertFalse(res_neg.success)
        self.assertEqual(res_neg.actual_change, 0)
        self.assertIn("positive", res_neg.reason)

        # Low-level model setter rejects negative bonus
        with self.assertRaises(ValueError):
            self.pika.set_trained_stat("attack", -1)

    def test_07_rejection_of_unsupported_stat_names(self) -> None:
        """Stats outside of Attack, Defense, and Speed are rejected cleanly."""
        res_spatk = self.manager.train_stat(self.pika, "special_attack", amount=5)
        self.assertFalse(res_spatk.success)
        self.assertIn("Unsupported", res_spatk.reason)

        res_hp = self.manager.train_stat(self.pika, "hp", amount=5)
        self.assertFalse(res_hp.success)
        self.assertIn("Unsupported", res_hp.reason)

    def test_08_rejection_of_fainted_pokemon(self) -> None:
        """Fainted Pokemon (HP <= 0) cannot undergo training."""
        self.pika.current_hp = 0
        self.assertTrue(self.pika.is_fainted)

        res = self.manager.train_stat(self.pika, "attack", amount=5)
        self.assertFalse(res.success)
        self.assertEqual(res.actual_change, 0)
        self.assertIn("fainted", res.reason)

    def test_09_invalid_input_handling(self) -> None:
        """Non-Pokemon objects and non-integer amounts are handled safely."""
        res_bad_mon = self.manager.train_stat("NotAPokemon", "attack", amount=5)  # type: ignore
        self.assertFalse(res_bad_mon.success)
        self.assertIn("Invalid pokemon", res_bad_mon.reason)

        res_bad_amt = self.manager.train_stat(self.pika, "attack", amount="five")  # type: ignore
        self.assertFalse(res_bad_amt.success)
        self.assertIn("integer", res_bad_amt.reason)

        # Model setter validates types
        with self.assertRaises(TypeError):
            self.pika.set_trained_stat("attack", "five")  # type: ignore

    def test_10_only_target_pokemon_changes(self) -> None:
        """Training one Pokemon does not mutate another Pokemon of the same species."""
        pika1 = Pokemon(species=PIKACHU, personality=self.personality)
        pika2 = Pokemon(species=PIKACHU, personality=self.personality)

        self.assertEqual(pika1.attack, 55)
        self.assertEqual(pika2.attack, 55)

        self.manager.train_attack(pika1, amount=15)
        self.assertEqual(pika1.attack, 70)
        self.assertEqual(pika2.attack, 55)  # Completely isolated

    def test_11_species_base_stats_remain_unchanged(self) -> None:
        """Training an instance never mutates the underlying PokemonSpecies blueprint."""
        self.assertEqual(PIKACHU.base_attack, 55)
        self.assertEqual(PIKACHU.base_defense, 40)
        self.assertEqual(PIKACHU.base_speed, 90)

        self.manager.train_attack(self.pika, amount=20)
        self.assertEqual(self.pika.attack, 75)

        # Species template remains untouched
        self.assertEqual(PIKACHU.base_attack, 55)
        self.assertEqual(self.pika.species.base_attack, 55)
        self.assertEqual(self.pika.base_attack, 55)

    def test_12_untrained_pokemon_retain_expected_stats(self) -> None:
        """Untrained Pokemon continue to report base stats identically to before."""
        self.assertEqual(self.pika.attack, self.pika.species.base_attack)
        self.assertEqual(self.pika.defense, self.pika.species.base_defense)
        self.assertEqual(self.pika.speed, self.pika.species.base_speed)
        self.assertEqual(self.pika.trained_attack, 0)
        self.assertEqual(self.pika.trained_defense, 0)
        self.assertEqual(self.pika.trained_speed, 0)

    def test_13_battle_damage_reflects_trained_attack_and_defense(self) -> None:
        """Damage calculator scales up with trained Attack and mitigates with trained Defense."""
        attacker = Pokemon(species=PIKACHU, personality=self.personality)
        defender = Pokemon(species=SQUIRTLE, personality=self.personality)

        # Baseline damage (no randomness)
        dmg_baseline = calculate_damage(
            attacker=attacker,
            defender=defender,
            attack=TACKLE,
            use_random_factor=False,
        ).damage

        # Train attacker's Attack (+25)
        self.manager.train_attack(attacker, amount=25)
        self.assertEqual(attacker.attack, 80)
        dmg_trained_atk = calculate_damage(
            attacker=attacker,
            defender=defender,
            attack=TACKLE,
            use_random_factor=False,
        ).damage
        self.assertGreater(dmg_trained_atk, dmg_baseline)

        # Train defender's Defense (+30)
        self.manager.train_defense(defender, amount=30)
        self.assertEqual(defender.defense, 95)
        dmg_trained_def = calculate_damage(
            attacker=attacker,
            defender=defender,
            attack=TACKLE,
            use_random_factor=False,
        ).damage
        self.assertLess(dmg_trained_def, dmg_trained_atk)

    def test_14_turn_order_reflects_trained_speed(self) -> None:
        """Speed training correctly inverts turn order in turn-based battles."""
        # Normally Pikachu (Speed 90) is faster than Squirtle (Speed 43)
        fast_pika = Pokemon(species=PIKACHU, personality=self.personality)
        slow_squirtle = Pokemon(species=SQUIRTLE, personality=self.personality)
        fast_pika.assign_attack(THUNDER_SHOCK)
        slow_squirtle.assign_attack(WATER_GUN)

        battle1 = Battle(pokemon1=fast_pika, pokemon2=slow_squirtle)
        order1 = battle1._determine_turn_order(THUNDER_SHOCK, WATER_GUN)
        # Pikachu acts first
        self.assertIs(order1[0][0], fast_pika)

        # Now train Squirtle's Speed by +55: 43 + 55 = 98 (faster than Pikachu's 90)
        self.manager.train_speed(slow_squirtle, amount=55)
        self.assertEqual(slow_squirtle.speed, 98)
        self.assertGreater(slow_squirtle.speed, fast_pika.speed)

        battle2 = Battle(pokemon1=fast_pika, pokemon2=slow_squirtle)
        order2 = battle2._determine_turn_order(THUNDER_SHOCK, WATER_GUN)
        # Squirtle now acts first!
        self.assertIs(order2[0][0], slow_squirtle)

    def test_15_existing_level_up_and_hp_behavior_intact(self) -> None:
        """Training does not mutate HP/level/bond/obedience, and level up preserves training."""
        self.assertEqual(self.pika.current_hp, 13)
        self.assertEqual(self.pika.max_hp, 13)
        self.assertEqual(self.pika.level, 1)
        self.assertEqual(self.pika.bond, 0)
        self.assertEqual(self.pika.obedience, 100)

        self.manager.train_attack(self.pika, amount=10)
        self.assertEqual(self.pika.attack, 65)

        # HP, level, bond, obedience unchanged
        self.assertEqual(self.pika.current_hp, 13)
        self.assertEqual(self.pika.max_hp, 13)
        self.assertEqual(self.pika.level, 1)
        self.assertEqual(self.pika.bond, 0)
        self.assertEqual(self.pika.obedience, 100)

        # Level up still works as expected
        apply_experience(self.pika, 150)
        self.assertEqual(self.pika.level, 2)
        self.assertEqual(self.pika.max_hp, 15)
        # Trained stat is fully preserved after level up
        self.assertEqual(self.pika.attack, 65)
        self.assertEqual(self.pika.trained_attack, 10)


if __name__ == "__main__":
    unittest.main()
