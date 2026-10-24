"""
Unit tests for the Pokémon data foundation.

Tests verify:
1. A species can be created.
2. An individual Pokémon can be created from a species.
3. The Pokémon receives the correct species information.
4. Maximum HP is calculated.
5. Current HP works correctly.
6. Personality values are stored correctly.
7. Invalid personality values are rejected.
8. Invalid Pokémon values such as negative level/XP are rejected.
9. Attacks can be assigned to Pokémon.
10. Multiple Pokémon instances of the same species can have different levels/personality/bond values.
"""
import unittest

from src.models.pokemon_type import PokemonType
from src.models.ability import Ability
from src.models.attack import Attack
from src.models.personality import Personality
from src.models.species import PokemonSpecies
from src.models.pokemon import Pokemon
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDERBOLT, QUICK_ATTACK, TACKLE


class TestPokemonFoundation(unittest.TestCase):
    """Test suite covering species, individual Pokémon, personality, stats, and attacks."""

    def setUp(self) -> None:
        """Set up standard sample objects for tests."""
        self.default_personality = Personality(
            aggression=40,
            curiosity=75,
            fear=20,
            sociability=85,
            loyalty=90,
            confidence=60,
        )

    # 1. A species can be created.
    def test_01_species_can_be_created(self) -> None:
        species = PokemonSpecies(
            name="Bulbasaur",
            primary_type=PokemonType.GRASS,
            base_hp=45,
            base_attack=49,
            base_defense=49,
            base_speed=45,
        )
        self.assertEqual(species.name, "Bulbasaur")
        self.assertEqual(species.primary_type, PokemonType.GRASS)
        self.assertEqual(species.base_hp, 45)
        self.assertEqual(species.types, (PokemonType.GRASS,))

        # Verify species validation
        with self.assertRaises(ValueError):
            PokemonSpecies(
                name="",
                primary_type=PokemonType.GRASS,
                base_hp=45,
                base_attack=49,
                base_defense=49,
                base_speed=45,
            )

        with self.assertRaises(ValueError):
            PokemonSpecies(
                name="InvalidStatMon",
                primary_type=PokemonType.GRASS,
                base_hp=-10,
                base_attack=49,
                base_defense=49,
                base_speed=45,
            )

    # 2. An individual Pokémon can be created from a species.
    def test_02_individual_pokemon_can_be_created(self) -> None:
        mon = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=5,
        )
        self.assertIsInstance(mon, Pokemon)
        self.assertIsNotNone(mon.unique_id)
        self.assertEqual(mon.level, 5)

    # 3. The Pokémon receives the correct species information.
    def test_03_pokemon_receives_correct_species_info(self) -> None:
        mon = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=5,
        )
        self.assertEqual(mon.species.name, "Pikachu")
        self.assertEqual(mon.species.primary_type, PokemonType.ELECTRIC)
        self.assertEqual(mon.species.base_hp, 11)
        self.assertEqual(mon.species.base_attack, 55)
        self.assertEqual(mon.species.base_defense, 40)
        self.assertEqual(mon.species.base_speed, 90)

    # 4. Maximum HP is calculated.
    def test_04_maximum_hp_is_calculated(self) -> None:
        # Formula: base_hp + (level * 2)
        # Pikachu base HP = 11
        mon_lvl_5 = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=5,
        )
        expected_hp_lvl_5 = 11 + (5 * 2)  # 21
        self.assertEqual(mon_lvl_5.max_hp, expected_hp_lvl_5)

        mon_lvl_50 = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=50,
        )
        expected_hp_lvl_50 = 11 + (50 * 2)  # 111
        self.assertEqual(mon_lvl_50.max_hp, expected_hp_lvl_50)

    # 5. Current HP works correctly.
    def test_05_current_hp_works_correctly(self) -> None:
        mon = Pokemon(
            species=CHARMANDER,
            personality=self.default_personality,
            level=10,
        )
        # Default current_hp should equal max_hp
        self.assertEqual(mon.current_hp, mon.max_hp)

        # Taking damage
        mon.current_hp = 20
        self.assertEqual(mon.current_hp, 20)

        # Current HP cannot exceed max_hp
        with self.assertRaises(ValueError):
            mon.current_hp = mon.max_hp + 1

        # Current HP cannot be negative
        with self.assertRaises(ValueError):
            mon.current_hp = -1

    def test_take_damage_and_heal_handling(self) -> None:
        mon = Pokemon(
            species=CHARMANDER,
            personality=self.default_personality,
            level=10,
        )
        max_hp = mon.max_hp

        # Normal damage
        dealt = mon.take_damage(15)
        self.assertEqual(dealt, 15)
        self.assertEqual(mon.current_hp, max_hp - 15)
        self.assertFalse(mon.is_fainted)
        self.assertTrue(mon.can_battle)

        # Clamping at 0 on excess damage
        dealt_excess = mon.take_damage(1000)
        self.assertEqual(dealt_excess, max_hp - 15)
        self.assertEqual(mon.current_hp, 0)
        self.assertTrue(mon.is_fainted)
        self.assertFalse(mon.can_battle)

        # Rejection of negative damage
        with self.assertRaises(ValueError):
            mon.take_damage(-5)

        # Rejection of invalid types for damage
        with self.assertRaises(TypeError):
            mon.take_damage("10")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            mon.take_damage(True)  # type: ignore[arg-type]

        # Normal heal
        healed = mon.heal(20)
        self.assertEqual(healed, 20)
        self.assertEqual(mon.current_hp, 20)
        self.assertFalse(mon.is_fainted)
        self.assertTrue(mon.can_battle)

        # Clamping at max_hp on excess heal
        healed_excess = mon.heal(1000)
        self.assertEqual(healed_excess, max_hp - 20)
        self.assertEqual(mon.current_hp, max_hp)

        # Rejection of negative healing
        with self.assertRaises(ValueError):
            mon.heal(-10)

        # Rejection of invalid types for healing
        with self.assertRaises(TypeError):
            mon.heal("20")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            mon.heal(False)  # type: ignore[arg-type]

        # Zero damage and zero heal
        self.assertEqual(mon.take_damage(0), 0)
        self.assertEqual(mon.heal(0), 0)

    # 6. Personality values are stored correctly.
    def test_06_personality_values_stored_correctly(self) -> None:
        pers = Personality(
            aggression=15,
            curiosity=95,
            fear=30,
            sociability=70,
            loyalty=100,
            confidence=50,
        )
        self.assertEqual(pers.aggression, 15)
        self.assertEqual(pers.curiosity, 95)
        self.assertEqual(pers.fear, 30)
        self.assertEqual(pers.sociability, 70)
        self.assertEqual(pers.loyalty, 100)
        self.assertEqual(pers.confidence, 50)

        mon = Pokemon(species=SQUIRTLE, personality=pers, level=5)
        self.assertEqual(mon.personality.aggression, 15)
        self.assertEqual(mon.personality.loyalty, 100)

    # 7. Invalid personality values are rejected.
    def test_07_invalid_personality_values_rejected(self) -> None:
        # Negative value (< 0)
        with self.assertRaises(ValueError):
            Personality(
                aggression=-5,
                curiosity=50,
                fear=50,
                sociability=50,
                loyalty=50,
                confidence=50,
            )

        # Exceeds 100 (> 100)
        with self.assertRaises(ValueError):
            Personality(
                aggression=50,
                curiosity=101,
                fear=50,
                sociability=50,
                loyalty=50,
                confidence=50,
            )

        # Non-numeric value
        with self.assertRaises(TypeError):
            Personality(
                aggression="high",  # type: ignore[arg-type]
                curiosity=50,
                fear=50,
                sociability=50,
                loyalty=50,
                confidence=50,
            )

    # 8. Invalid Pokémon values such as negative level/XP are rejected.
    def test_08_invalid_pokemon_values_rejected(self) -> None:
        # Non-positive level
        with self.assertRaises(ValueError):
            Pokemon(
                species=PIKACHU,
                personality=self.default_personality,
                level=0,
            )

        with self.assertRaises(ValueError):
            Pokemon(
                species=PIKACHU,
                personality=self.default_personality,
                level=-3,
            )

        # Negative experience
        with self.assertRaises(ValueError):
            Pokemon(
                species=PIKACHU,
                personality=self.default_personality,
                level=5,
                experience=-100,
            )

        # Negative bond or obedience
        with self.assertRaises(ValueError):
            Pokemon(
                species=PIKACHU,
                personality=self.default_personality,
                bond=-1,
            )

        with self.assertRaises(ValueError):
            Pokemon(
                species=PIKACHU,
                personality=self.default_personality,
                obedience=105,
            )

    # 9. Attacks can be assigned to Pokémon.
    def test_09_attacks_can_be_assigned_to_pokemon(self) -> None:
        mon = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=10,
        )
        self.assertEqual(len(mon.attacks), 0)

        mon.assign_attack(QUICK_ATTACK)
        mon.assign_attack(THUNDERBOLT)

        self.assertEqual(len(mon.attacks), 2)
        self.assertIn(QUICK_ATTACK, mon.attacks)
        self.assertIn(THUNDERBOLT, mon.attacks)

        # Assigning an invalid object raises TypeError
        with self.assertRaises(TypeError):
            mon.assign_attack("Tackle")  # type: ignore[arg-type]

        # Duplicate attacks should not be added twice
        mon.assign_attack(QUICK_ATTACK)
        self.assertEqual(len(mon.attacks), 2)

    # 10. Multiple Pokémon instances of the same species can have different levels/personality/bond values.
    def test_10_multiple_instances_have_independent_state(self) -> None:
        wild_personality = Personality(
            aggression=80,
            curiosity=20,
            fear=60,
            sociability=10,
            loyalty=15,
            confidence=30,
        )
        partner_personality = Personality(
            aggression=10,
            curiosity=85,
            fear=10,
            sociability=90,
            loyalty=100,
            confidence=75,
        )

        wild_pikachu = Pokemon(
            species=PIKACHU,
            personality=wild_personality,
            level=3,
            bond=0,
            obedience=30,
        )

        partner_pikachu = Pokemon(
            species=PIKACHU,
            personality=partner_personality,
            level=25,
            bond=95,
            obedience=100,
            nickname="Sparky",
        )

        # Same species blueprint
        self.assertIs(wild_pikachu.species, partner_pikachu.species)

        # Different instances and IDs
        self.assertNotEqual(wild_pikachu.unique_id, partner_pikachu.unique_id)

        # Different levels and derived stats
        self.assertEqual(wild_pikachu.level, 3)
        self.assertEqual(partner_pikachu.level, 25)
        self.assertNotEqual(wild_pikachu.max_hp, partner_pikachu.max_hp)

        # Different personalities
        self.assertEqual(wild_pikachu.personality.aggression, 80)
        self.assertEqual(partner_pikachu.personality.aggression, 10)

        # Different bond and obedience
        self.assertEqual(wild_pikachu.bond, 0)
        self.assertEqual(partner_pikachu.bond, 95)
        self.assertEqual(wild_pikachu.obedience, 30)
        self.assertEqual(partner_pikachu.obedience, 100)

        # Different nicknames
        self.assertEqual(wild_pikachu.display_name, "Pikachu")
        self.assertEqual(partner_pikachu.display_name, "Sparky")

    # Additional tests: Attack and Ability models
    def test_attack_and_ability_validation(self) -> None:
        # Valid attack
        atk = Attack(name="Water Gun", type=PokemonType.WATER, power=40, accuracy=100)
        self.assertEqual(atk.name, "Water Gun")

        # Invalid accuracy (> 100)
        with self.assertRaises(ValueError):
            Attack(name="Hyper Gun", type=PokemonType.WATER, power=100, accuracy=120)

        # Invalid power (< 0)
        with self.assertRaises(ValueError):
            Attack(name="Self Hurt", type=PokemonType.NORMAL, power=-10, accuracy=100)

        # Valid ability
        ab = Ability(name="Overgrow", description="Boosts grass moves.")
        self.assertEqual(ab.name, "Overgrow")

        # Empty ability name
        with self.assertRaises(ValueError):
            Ability(name="", description="Boosts grass moves.")


if __name__ == "__main__":
    unittest.main()
