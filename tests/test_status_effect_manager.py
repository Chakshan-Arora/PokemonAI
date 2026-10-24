"""
Unit tests for StatusEffectManager: status application, major conditions,
stat reductions, paralysis checks, end-of-turn damage, duration decrement, and expiration.
"""
import unittest
import random

from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.attack import Attack
from src.models.pokemon_type import PokemonType
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.models.status_effect import (
    StatusEffectType,
    AttackEffect,
    StatusEffect,
    DEFAULT_BURN_DAMAGE_FRACTION,
    DEFAULT_POISON_DAMAGE_FRACTION,
    DEFAULT_PARALYSIS_CHANCE,
    DEFAULT_STAT_REDUCTION_DURATION,
    DEFAULT_STAT_REDUCTION_MULTIPLIER,
)
from src.models.status_effect_manager import (
    StatusEffectManager,
    EffectApplicationResult,
    ActionCheckResult,
    EndOfTurnResult,
)


class TestStatusEffectManager(unittest.TestCase):
    """Test suite covering the standalone StatusEffectManager operations."""

    def setUp(self) -> None:
        self.rng = random.Random(42)
        self.manager = StatusEffectManager(rng=self.rng)
        self.personality = Personality(aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50)

    def _create_pokemon(self, species=PIKACHU, level=5, current_hp=None, trained_stats=None) -> Pokemon:
        return Pokemon(
            species=species,
            personality=self.personality,
            level=level,
            current_hp=current_hp,
            trained_stats=trained_stats,
        )

    def test_01_apply_valid_persistent_condition_burn(self) -> None:
        """Applying Burn succeeds on an un-afflicted Pokemon."""
        pkmn = self._create_pokemon()
        burn_effect = AttackEffect(effect_type=StatusEffectType.BURN, chance=100)

        result = self.manager.apply_effect(pkmn, burn_effect)
        self.assertTrue(result.success)
        self.assertTrue(result.applied)
        self.assertIs(result.pokemon, pkmn)
        self.assertTrue(self.manager.has_effect(pkmn, StatusEffectType.BURN))
        self.assertFalse(self.manager.has_effect(pkmn, StatusEffectType.POISON))

        major = self.manager.get_major_condition(pkmn)
        self.assertIsNotNone(major)
        self.assertEqual(major.effect_type, StatusEffectType.BURN)

    def test_02_deterministic_application_chance(self) -> None:
        """AttackEffect application chance adheres to the roll (<= chance succeeds, > chance fails)."""
        pkmn = self._create_pokemon()
        effect = AttackEffect(effect_type=StatusEffectType.BURN, chance=30)

        # Roll 30 <= 30 -> Success
        res_hit = self.manager.apply_effect(pkmn, effect, roll_override=30)
        self.assertTrue(res_hit.success)
        self.assertEqual(res_hit.roll, 30)
        self.assertTrue(self.manager.has_effect(pkmn, StatusEffectType.BURN))

        # Clear and test miss
        self.manager.clear_effects(pkmn)
        # Roll 31 > 30 -> Failure
        res_miss = self.manager.apply_effect(pkmn, effect, roll_override=31)
        self.assertFalse(res_miss.success)
        self.assertEqual(res_miss.roll, 31)
        self.assertFalse(self.manager.has_effect(pkmn, StatusEffectType.BURN))

    def test_03_major_condition_conflict_handling(self) -> None:
        """A Pokemon with a major condition cannot receive a second different major condition."""
        pkmn = self._create_pokemon()
        self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.BURN, chance=100))

        # Attempt to apply Poison
        res_poison = self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.POISON, chance=100))
        self.assertFalse(res_poison.success)
        self.assertIn("already has major status condition Burn", res_poison.reason)
        self.assertFalse(self.manager.has_effect(pkmn, StatusEffectType.POISON))

        # Attempt to apply Paralysis
        res_para = self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.PARALYSIS, chance=100))
        self.assertFalse(res_para.success)
        self.assertIn("cannot be afflicted with Paralysis", res_para.reason)
        self.assertFalse(self.manager.has_effect(pkmn, StatusEffectType.PARALYSIS))

    def test_04_duplicate_major_condition_rejected(self) -> None:
        """Attempting to apply the same major condition twice is rejected cleanly."""
        pkmn = self._create_pokemon()
        self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.BURN, chance=100))

        res_dup = self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.BURN, chance=100))
        self.assertFalse(res_dup.success)
        self.assertIn("already afflicted with Burn", res_dup.reason)

    def test_05_fainted_pokemon_cannot_receive_effects(self) -> None:
        """A fainted Pokemon (HP == 0) cannot receive status effects."""
        pkmn = self._create_pokemon()
        pkmn.take_damage(pkmn.max_hp)
        self.assertTrue(pkmn.is_fainted)

        result = self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.BURN, chance=100))
        self.assertFalse(result.success)
        self.assertIn("has fainted", result.reason)
        self.assertFalse(self.manager.has_effect(pkmn, StatusEffectType.BURN))

    def test_06_burn_end_of_turn_damage(self) -> None:
        """Burn deals damage at end of turn (at least 1 HP, based on max HP fraction)."""
        pkmn = self._create_pokemon(level=10)
        initial_hp = pkmn.current_hp
        self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.BURN, chance=100))

        eot_res = self.manager.process_end_of_turn(pkmn)
        expected_dmg = max(1, int(pkmn.max_hp * DEFAULT_BURN_DAMAGE_FRACTION))

        self.assertEqual(eot_res.damage_taken, expected_dmg)
        self.assertEqual(pkmn.current_hp, initial_hp - expected_dmg)
        self.assertEqual(len(eot_res.effects_processed), 1)
        self.assertEqual(eot_res.effects_processed[0].effect_type, StatusEffectType.BURN)

    def test_07_poison_end_of_turn_damage(self) -> None:
        """Poison deals damage at end of turn without expiring."""
        pkmn = self._create_pokemon(level=10)
        initial_hp = pkmn.current_hp
        self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.POISON, chance=100))

        eot_res = self.manager.process_end_of_turn(pkmn)
        expected_dmg = max(1, int(pkmn.max_hp * DEFAULT_POISON_DAMAGE_FRACTION))

        self.assertEqual(eot_res.damage_taken, expected_dmg)
        self.assertEqual(pkmn.current_hp, initial_hp - expected_dmg)
        self.assertTrue(self.manager.has_effect(pkmn, StatusEffectType.POISON))

    def test_08_paralysis_action_check(self) -> None:
        """Paralysis action check deterministically blocks action when roll <= paralysis_chance."""
        pkmn = self._create_pokemon()
        self.manager.apply_effect(
            pkmn,
            AttackEffect(effect_type=StatusEffectType.PARALYSIS, chance=100, paralysis_chance=25),
        )

        # Roll 25 <= 25 -> Action prevented
        res_blocked = self.manager.check_can_act(pkmn, roll_override=25)
        self.assertFalse(res_blocked.can_act)
        self.assertTrue(res_blocked.paralyzed)
        self.assertIn("paralyzed", res_blocked.reason.lower())

        # Roll 26 > 25 -> Action succeeds
        res_free = self.manager.check_can_act(pkmn, roll_override=26)
        self.assertTrue(res_free.can_act)
        self.assertTrue(res_free.paralyzed)
        self.assertIn("despite paralysis", res_free.reason)

    def test_09_temporary_attack_reduction_and_effective_stat(self) -> None:
        """Attack reduction reduces effective Attack without mutating permanent or base stats."""
        pkmn = self._create_pokemon(species=CHARMANDER, trained_stats={"attack": 10})
        unmodified_attack = pkmn.attack  # species.base_attack (52) + 10 = 62

        # Apply 20% attack reduction (multiplier 0.8) for 2 turns
        eff = AttackEffect(
            effect_type=StatusEffectType.ATTACK_REDUCTION,
            chance=100,
            duration=2,
            multiplier=0.8,
        )
        self.manager.apply_effect(pkmn, eff)

        effective_atk = self.manager.get_effective_stat(pkmn, "attack")
        self.assertEqual(effective_atk, int(62 * 0.8))  # 49
        self.assertEqual(pkmn.attack, 62)  # Permanent stat completely unmutated
        self.assertEqual(pkmn.trained_attack, 10)  # Permanent training bonus intact
        self.assertEqual(pkmn.species.base_attack, 52)  # Blueprint intact

    def test_10_temporary_defense_reduction(self) -> None:
        """Defense reduction reduces effective Defense stat."""
        pkmn = self._create_pokemon(species=SQUIRTLE)
        unmodified_def = pkmn.defense

        eff = AttackEffect(
            effect_type=StatusEffectType.DEFENSE_REDUCTION,
            chance=100,
            duration=3,
            multiplier=0.8,
        )
        self.manager.apply_effect(pkmn, eff)

        effective_def = self.manager.get_effective_stat(pkmn, "defense")
        self.assertEqual(effective_def, int(unmodified_def * 0.8))
        self.assertLess(effective_def, unmodified_def)

    def test_11_duration_decrement_and_expiration_restores_stats(self) -> None:
        """Temporary effects decrement duration each turn and restore base effective stats upon expiration."""
        pkmn = self._create_pokemon()
        initial_atk = pkmn.attack

        eff = AttackEffect(
            effect_type=StatusEffectType.ATTACK_REDUCTION,
            chance=100,
            duration=2,
            multiplier=0.8,
        )
        self.manager.apply_effect(pkmn, eff)
        self.assertEqual(self.manager.get_effective_stat(pkmn, "attack"), int(initial_atk * 0.8))

        # Turn 1 end
        res1 = self.manager.process_end_of_turn(pkmn)
        self.assertEqual(len(res1.expired_effects), 0)
        self.assertEqual(self.manager.get_effective_stat(pkmn, "attack"), int(initial_atk * 0.8))

        # Turn 2 end -> Expires!
        res2 = self.manager.process_end_of_turn(pkmn)
        self.assertIn(StatusEffectType.ATTACK_REDUCTION, res2.expired_effects)
        self.assertFalse(self.manager.has_effect(pkmn, StatusEffectType.ATTACK_REDUCTION))

        # Effective attack is fully restored
        self.assertEqual(self.manager.get_effective_stat(pkmn, "attack"), initial_atk)

    def test_12_multiple_temporary_stat_effects_coexist_and_stack(self) -> None:
        """Multiple temporary stat reductions can coexist with a major condition and stack multiplicatively."""
        pkmn = self._create_pokemon()
        initial_atk = pkmn.attack
        initial_def = pkmn.defense

        # Apply Burn
        self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.BURN, chance=100))
        # Apply Attack reduction (0.8x)
        self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.ATTACK_REDUCTION, chance=100, multiplier=0.8, duration=3))
        # Apply Defense reduction (0.8x)
        self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.DEFENSE_REDUCTION, chance=100, multiplier=0.8, duration=3))
        # Apply second Attack reduction (0.8x)
        self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.ATTACK_REDUCTION, chance=100, multiplier=0.8, duration=3))

        self.assertTrue(self.manager.has_effect(pkmn, StatusEffectType.BURN))
        self.assertTrue(self.manager.has_effect(pkmn, StatusEffectType.ATTACK_REDUCTION))
        self.assertTrue(self.manager.has_effect(pkmn, StatusEffectType.DEFENSE_REDUCTION))

        # Attack has two 0.8 multipliers stacked: 0.8 * 0.8 = 0.64
        expected_atk = max(1, int(initial_atk * 0.8 * 0.8))
        self.assertEqual(self.manager.get_effective_stat(pkmn, "attack"), expected_atk)
        # Defense has one 0.8 multiplier
        expected_def = max(1, int(initial_def * 0.8))
        self.assertEqual(self.manager.get_effective_stat(pkmn, "defense"), expected_def)

    def test_13_stat_multiplier_cannot_produce_invalid_or_negative_stats(self) -> None:
        """Extreme stat reductions are clamped at a floor and never produce zero or negative stats."""
        pkmn = self._create_pokemon()
        # Apply multiple harsh reductions
        for _ in range(10):
            self.manager.apply_effect(
                pkmn,
                AttackEffect(effect_type=StatusEffectType.ATTACK_REDUCTION, chance=100, multiplier=0.5, duration=3),
            )

        eff_atk = self.manager.get_effective_stat(pkmn, "attack")
        self.assertGreaterEqual(eff_atk, 1)

    def test_14_clear_effects_removes_all_active_effects(self) -> None:
        """clear_effects completely purges all active conditions and restores stats."""
        pkmn = self._create_pokemon()
        self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.BURN, chance=100))
        self.manager.apply_effect(pkmn, AttackEffect(effect_type=StatusEffectType.ATTACK_REDUCTION, chance=100, duration=3))

        self.assertEqual(len(self.manager.get_effects(pkmn)), 2)
        self.manager.clear_effects(pkmn)

        self.assertEqual(len(self.manager.get_effects(pkmn)), 0)
        self.assertFalse(self.manager.has_effect(pkmn, StatusEffectType.BURN))
        self.assertEqual(self.manager.get_effective_stat(pkmn, "attack"), pkmn.attack)

    def test_15_invalid_inputs_handled_safely(self) -> None:
        """Invalid types passed to manager return clean failure results without raising unhandled errors."""
        res1 = self.manager.apply_effect("not a pokemon", AttackEffect(effect_type=StatusEffectType.BURN))  # type: ignore
        self.assertFalse(res1.success)

        pkmn = self._create_pokemon()
        res2 = self.manager.apply_effect(pkmn, "not an effect")  # type: ignore
        self.assertFalse(res2.success)


if __name__ == "__main__":
    unittest.main()
