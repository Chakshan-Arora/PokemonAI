"""
Unit tests for the damage calculation engine.

Tests verify:
3. Damage is never negative.
4. Higher defense generally reduces damage.
5. Super-effective attacks deal more damage than otherwise identical neutral attacks.
"""
import random
import unittest

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.species import PokemonSpecies
from src.models.pokemon_type import PokemonType
from src.models.attack import Attack
from src.models.damage_calculator import calculate_damage, DamageResult
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, TACKLE, EMBER, WATER_GUN


class TestDamageCalculator(unittest.TestCase):
    """Test suite for damage formula, multipliers, defense mitigation, and RNG."""

    def setUp(self) -> None:
        self.default_personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )
        self.attacker = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)
        self.defender = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5)

    # 3. Damage is never negative.
    def test_03_damage_is_never_negative(self) -> None:
        dmg = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=THUNDER_SHOCK,
            type_effectiveness=1.0,
            use_random_factor=False,
        )
        self.assertIsInstance(dmg, DamageResult)
        self.assertGreaterEqual(dmg.damage, 0)
        self.assertGreater(dmg.damage, 0)

        # Zero power move
        zero_power_attack = Attack(name="Growl", type=PokemonType.NORMAL, power=0, accuracy=100)
        dmg_zero = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=zero_power_attack,
            type_effectiveness=1.0,
        )
        self.assertIsInstance(dmg_zero, DamageResult)
        self.assertEqual(dmg_zero.damage, 0)

        # Zero effectiveness (immunity)
        dmg_immune = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=THUNDER_SHOCK,
            type_effectiveness=0.0,
        )
        self.assertIsInstance(dmg_immune, DamageResult)
        self.assertEqual(dmg_immune.damage, 0)

    # 4. Higher defense generally reduces damage.
    def test_04_higher_defense_reduces_damage(self) -> None:
        low_def_species = PokemonSpecies(
            name="LowDef",
            primary_type=PokemonType.NORMAL,
            base_hp=50,
            base_attack=50,
            base_defense=20,
            base_speed=50,
        )
        high_def_species = PokemonSpecies(
            name="HighDef",
            primary_type=PokemonType.NORMAL,
            base_hp=50,
            base_attack=50,
            base_defense=100,
            base_speed=50,
        )

        low_def_mon = Pokemon(species=low_def_species, personality=self.default_personality, level=5)
        high_def_mon = Pokemon(species=high_def_species, personality=self.default_personality, level=5)

        dmg_against_low = calculate_damage(
            attacker=self.attacker,
            defender=low_def_mon,
            attack=TACKLE,
            type_effectiveness=1.0,
            use_random_factor=False,
        )
        dmg_against_high = calculate_damage(
            attacker=self.attacker,
            defender=high_def_mon,
            attack=TACKLE,
            type_effectiveness=1.0,
            use_random_factor=False,
        )

        self.assertGreater(dmg_against_low.damage, dmg_against_high.damage)

    # 5. Super-effective attacks deal more damage than otherwise identical neutral attacks.
    def test_05_super_effective_deals_more_damage_than_neutral(self) -> None:
        dmg_neutral = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=THUNDER_SHOCK,
            type_effectiveness=1.0,
            use_random_factor=False,
        )
        dmg_super = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=THUNDER_SHOCK,
            type_effectiveness=2.0,
            use_random_factor=False,
        )
        dmg_resisted = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=THUNDER_SHOCK,
            type_effectiveness=0.5,
            use_random_factor=False,
        )

        self.assertGreater(dmg_super.damage, dmg_neutral.damage)
        self.assertGreater(dmg_neutral.damage, dmg_resisted.damage)

    def test_injected_rng_reproducibility(self) -> None:
        rng1 = random.Random(999)
        rng2 = random.Random(999)

        dmg1 = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=THUNDER_SHOCK,
            rng=rng1,
        )
        dmg2 = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=THUNDER_SHOCK,
            rng=rng2,
        )

        self.assertEqual(dmg1.damage, dmg2.damage)
        self.assertEqual(dmg1.is_critical, dmg2.is_critical)
        self.assertEqual(dmg1.random_factor, dmg2.random_factor)

    def test_input_validation(self) -> None:
        with self.assertRaises(TypeError):
            calculate_damage("Pikachu", self.defender, THUNDER_SHOCK)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            calculate_damage(self.attacker, "Charmander", THUNDER_SHOCK)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            calculate_damage(self.attacker, self.defender, "Thunder Shock")  # type: ignore[arg-type]

    def test_bond_multiplier_and_critical_hits(self) -> None:
        # Bond 0 vs Bond 100
        dmg_bond0 = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=THUNDER_SHOCK,
            use_random_factor=False,
            bond=0,
            use_critical=False,
        )
        dmg_bond100 = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=THUNDER_SHOCK,
            use_random_factor=False,
            bond=100,
            use_critical=False,
        )
        self.assertEqual(dmg_bond0.bond_multiplier, 1.0)
        self.assertEqual(dmg_bond100.bond_multiplier, 1.15)
        self.assertGreaterEqual(dmg_bond100.damage, dmg_bond0.damage)

        # Critical hit roll simulation
        # Seed where rng.random() < 0.0625
        class MockCritRng:
            def random(self) -> float:
                return 0.01  # guaranteed crit
            def uniform(self, a: float, b: float) -> float:
                return 1.0

        res_crit = calculate_damage(
            attacker=self.attacker,
            defender=self.defender,
            attack=THUNDER_SHOCK,
            rng=MockCritRng(),
            bond=0,
            use_critical=True,
        )
        self.assertTrue(res_crit.is_critical)
        self.assertGreater(res_crit.damage, dmg_bond0.damage)


if __name__ == "__main__":
    unittest.main()
