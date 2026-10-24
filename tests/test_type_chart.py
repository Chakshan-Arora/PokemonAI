"""
Unit tests for the Pokemon type effectiveness chart and dual-type calculations.

Tests verify:
1. Type chart returns the expected multipliers.
2. Dual-type effectiveness combines correctly.
"""
import unittest

from src.models.pokemon_type import PokemonType
from src.models.attack import Attack
from src.models.species import PokemonSpecies
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.data.type_chart import (
    TYPE_EFFECTIVENESS_CHART,
    get_type_effectiveness,
    get_effectiveness_against_types,
    get_effectiveness_against_pokemon,
)
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, EMBER, WATER_GUN, VINE_WHIP, TACKLE


class TestTypeChart(unittest.TestCase):
    """Test suite for type matchups and multiplier calculations."""

    def setUp(self) -> None:
        self.default_personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )

    # 1. Type chart returns the expected multipliers.
    def test_01_type_chart_expected_multipliers(self) -> None:
        # Super effective (2.0)
        self.assertEqual(get_type_effectiveness(PokemonType.FIRE, PokemonType.GRASS), 2.0)
        self.assertEqual(get_type_effectiveness(PokemonType.WATER, PokemonType.FIRE), 2.0)
        self.assertEqual(get_type_effectiveness(PokemonType.GRASS, PokemonType.WATER), 2.0)
        self.assertEqual(get_type_effectiveness(PokemonType.ELECTRIC, PokemonType.WATER), 2.0)

        # Not very effective (0.5)
        self.assertEqual(get_type_effectiveness(PokemonType.FIRE, PokemonType.WATER), 0.5)
        self.assertEqual(get_type_effectiveness(PokemonType.FIRE, PokemonType.FIRE), 0.5)
        self.assertEqual(get_type_effectiveness(PokemonType.WATER, PokemonType.GRASS), 0.5)
        self.assertEqual(get_type_effectiveness(PokemonType.WATER, PokemonType.WATER), 0.5)
        self.assertEqual(get_type_effectiveness(PokemonType.GRASS, PokemonType.FIRE), 0.5)
        self.assertEqual(get_type_effectiveness(PokemonType.ELECTRIC, PokemonType.GRASS), 0.5)
        self.assertEqual(get_type_effectiveness(PokemonType.ELECTRIC, PokemonType.ELECTRIC), 0.5)

        # Neutral (1.0)
        self.assertEqual(get_type_effectiveness(PokemonType.NORMAL, PokemonType.NORMAL), 1.0)
        self.assertEqual(get_type_effectiveness(PokemonType.NORMAL, PokemonType.FIRE), 1.0)
        self.assertEqual(get_type_effectiveness(PokemonType.FIRE, PokemonType.NORMAL), 1.0)
        self.assertEqual(get_type_effectiveness(PokemonType.ELECTRIC, PokemonType.NORMAL), 1.0)
        self.assertEqual(get_type_effectiveness(PokemonType.ELECTRIC, PokemonType.FIRE), 1.0)

    # 2. Dual-type effectiveness combines correctly.
    def test_02_dual_type_effectiveness_combines_correctly(self) -> None:
        # Fire vs (Grass, Water) -> 2.0 * 0.5 = 1.0 (cancels out)
        mult_fire = get_effectiveness_against_types(
            PokemonType.FIRE, (PokemonType.GRASS, PokemonType.WATER)
        )
        self.assertEqual(mult_fire, 1.0)

        # Electric vs (Water, Normal) -> 2.0 * 1.0 = 2.0
        mult_elec = get_effectiveness_against_types(
            PokemonType.ELECTRIC, (PokemonType.WATER, PokemonType.NORMAL)
        )
        self.assertEqual(mult_elec, 2.0)

        # Water vs (Fire, Grass) -> 2.0 * 0.5 = 1.0
        mult_water = get_effectiveness_against_types(
            PokemonType.WATER, (PokemonType.FIRE, PokemonType.GRASS)
        )
        self.assertEqual(mult_water, 1.0)

        # Fire vs (Grass, Normal) -> 2.0 * 1.0 = 2.0
        mult_fire_dual = get_effectiveness_against_types(
            PokemonType.FIRE, (PokemonType.GRASS, PokemonType.NORMAL)
        )
        self.assertEqual(mult_fire_dual, 2.0)

        # Double resistance (0.25)
        # Water vs (Grass, Water) -> 0.5 * 0.5 = 0.25
        mult_double_resist_water = get_effectiveness_against_types(
            PokemonType.WATER, (PokemonType.GRASS, PokemonType.WATER)
        )
        self.assertEqual(mult_double_resist_water, 0.25)

        # Electric vs (Grass, Electric) -> 0.5 * 0.5 = 0.25
        mult_double_resist_elec = get_effectiveness_against_types(
            PokemonType.ELECTRIC, (PokemonType.GRASS, PokemonType.ELECTRIC)
        )
        self.assertEqual(mult_double_resist_elec, 0.25)

        # Single resistance against dual type (0.5 * 1.0 = 0.5)
        # Grass vs (Fire, Electric) -> 0.5 * 1.0 = 0.5
        mult_single_resist = get_effectiveness_against_types(
            PokemonType.GRASS, (PokemonType.FIRE, PokemonType.ELECTRIC)
        )
        self.assertEqual(mult_single_resist, 0.5)

        # Empty defending types returns 1.0
        self.assertEqual(get_effectiveness_against_types(PokemonType.NORMAL, ()), 1.0)

    def test_full_type_chart_all_25_matchups(self) -> None:
        """Exhaustively verify every single entry in the 5x5 chart."""
        expected_matrix = {
            PokemonType.NORMAL: {
                PokemonType.NORMAL: 1.0, PokemonType.FIRE: 1.0,
                PokemonType.WATER: 1.0, PokemonType.GRASS: 1.0, PokemonType.ELECTRIC: 1.0,
            },
            PokemonType.FIRE: {
                PokemonType.NORMAL: 1.0, PokemonType.FIRE: 0.5,
                PokemonType.WATER: 0.5, PokemonType.GRASS: 2.0, PokemonType.ELECTRIC: 1.0,
            },
            PokemonType.WATER: {
                PokemonType.NORMAL: 1.0, PokemonType.FIRE: 2.0,
                PokemonType.WATER: 0.5, PokemonType.GRASS: 0.5, PokemonType.ELECTRIC: 1.0,
            },
            PokemonType.GRASS: {
                PokemonType.NORMAL: 1.0, PokemonType.FIRE: 0.5,
                PokemonType.WATER: 2.0, PokemonType.GRASS: 0.5, PokemonType.ELECTRIC: 1.0,
            },
            PokemonType.ELECTRIC: {
                PokemonType.NORMAL: 1.0, PokemonType.FIRE: 1.0,
                PokemonType.WATER: 2.0, PokemonType.GRASS: 0.5, PokemonType.ELECTRIC: 0.5,
            },
        }
        for atk, def_map in expected_matrix.items():
            for dfn, expected_mult in def_map.items():
                actual_mult = get_type_effectiveness(atk, dfn)
                self.assertEqual(
                    actual_mult,
                    expected_mult,
                    f"Mismatch for {atk.name} vs {dfn.name}: expected {expected_mult}, got {actual_mult}",
                )

    def test_effectiveness_against_pokemon(self) -> None:
        pika = Pokemon(species=PIKACHU, personality=self.default_personality)
        squirtle = Pokemon(species=SQUIRTLE, personality=self.default_personality)
        charmander = Pokemon(species=CHARMANDER, personality=self.default_personality)

        # Thunder Shock (Electric) vs Squirtle (Water) -> 2.0
        self.assertEqual(get_effectiveness_against_pokemon(THUNDER_SHOCK, squirtle), 2.0)

        # Water Gun (Water) vs Charmander (Fire) -> 2.0
        self.assertEqual(get_effectiveness_against_pokemon(WATER_GUN, charmander), 2.0)

        # Ember (Fire) vs Squirtle (Water) -> 0.5
        self.assertEqual(get_effectiveness_against_pokemon(EMBER, squirtle), 0.5)

        # Tackle (Normal) vs Pikachu (Electric) -> 1.0
        self.assertEqual(get_effectiveness_against_pokemon(TACKLE, pika), 1.0)

        # Dual-type defending Pokemon (Water / Grass)
        lotad_species = PokemonSpecies(
            name="LotadDummy",
            primary_type=PokemonType.WATER,
            secondary_type=PokemonType.GRASS,
            base_hp=40,
            base_attack=30,
            base_defense=30,
            base_speed=30,
        )
        lotad = Pokemon(species=lotad_species, personality=self.default_personality)

        # Water vs Water/Grass -> 0.5 * 0.5 = 0.25 (double resist)
        self.assertEqual(get_effectiveness_against_pokemon(WATER_GUN, lotad), 0.25)
        # Fire vs Water/Grass -> 0.5 * 2.0 = 1.0 (neutral)
        self.assertEqual(get_effectiveness_against_pokemon(EMBER, lotad), 1.0)
        # Thunder Shock vs Water/Grass -> 2.0 * 0.5 = 1.0 (neutral)
        self.assertEqual(get_effectiveness_against_pokemon(THUNDER_SHOCK, lotad), 1.0)

    def test_type_chart_input_validation(self) -> None:
        with self.assertRaises(TypeError):
            get_type_effectiveness("Fire", PokemonType.WATER)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            get_type_effectiveness(PokemonType.FIRE, "Water")  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            get_effectiveness_against_pokemon("Thunder Shock", PIKACHU)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            get_effectiveness_against_pokemon(THUNDER_SHOCK, "Pikachu")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
