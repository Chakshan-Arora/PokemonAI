"""
Unit tests for the EncounterManager and wild encounter eligibility checks.

Tests verify:
13. A despawned Pokémon is no longer encounter-eligible through the area.
15. A player inside the encounter radius can trigger an eligible encounter result.
16. A player outside the encounter radius cannot trigger an encounter.
17. Species and area restrictions are respected by encounter checks.
"""
import unittest

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager, EncounterResult
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.spawn_config import PIKACHU_SPAWN_CONFIG, SQUIRTLE_SPAWN_CONFIG


class TestEncounterManager(unittest.TestCase):
    """Test suite covering encounter radius, position checks, and area restrictions."""

    def setUp(self) -> None:
        """Create sample area, Pokemon, manager, and encounter manager."""
        self.default_personality = Personality(
            aggression=30,
            curiosity=60,
            fear=20,
            sociability=70,
            loyalty=80,
            confidence=60,
        )

        self.forest_area = SpawnArea(
            area_id="forest",
            name="Viridian Forest",
            allowed_species=(PIKACHU,),
            max_active_pokemon=3,
            encounter_radius=10.0,
            enabled=True,
        )

        self.pikachu = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=4,
        )

        self.charmander = Pokemon(
            species=CHARMANDER,
            personality=self.default_personality,
            level=4,
        )

        self.encounter_mgr = EncounterManager()

    # 15. A player inside the encounter radius can trigger an eligible encounter result.
    def test_15_player_inside_encounter_radius_triggers_eligible_result(self) -> None:
        player_pos = (5.0, 5.0)
        pokemon_pos = (8.0, 5.0)  # Distance = 3.0m (radius = 10.0m)

        result = self.encounter_mgr.check_encounter(
            player_position=player_pos,
            pokemon_position=pokemon_pos,
            pokemon=self.pikachu,
            area=self.forest_area,
            is_active=True,
        )

        self.assertTrue(result.can_encounter)
        self.assertEqual(result.reason, "Encounter permitted.")
        self.assertAlmostEqual(result.distance, 3.0)
        self.assertIs(result.pokemon, self.pikachu)
        self.assertIs(result.area, self.forest_area)

    # 16. A player outside the encounter radius cannot trigger an encounter.
    def test_16_player_outside_encounter_radius_cannot_trigger_encounter(self) -> None:
        player_pos = (0.0, 0.0)
        pokemon_pos = (20.0, 0.0)  # Distance = 20.0m (radius = 10.0m)

        result = self.encounter_mgr.check_encounter(
            player_position=player_pos,
            pokemon_position=pokemon_pos,
            pokemon=self.pikachu,
            area=self.forest_area,
            is_active=True,
        )

        self.assertFalse(result.can_encounter)
        self.assertIn("outside encounter radius", result.reason)
        self.assertAlmostEqual(result.distance, 20.0)

    # 17. Species and area restrictions are respected by encounter checks.
    def test_17_species_and_area_restrictions_respected(self) -> None:
        player_pos = (0.0, 0.0)
        pokemon_pos = (2.0, 2.0)  # Close distance

        # Charmander is not allowed in forest_area (only PIKACHU is allowed)
        result_disallowed = self.encounter_mgr.check_encounter(
            player_position=player_pos,
            pokemon_position=pokemon_pos,
            pokemon=self.charmander,
            area=self.forest_area,
            is_active=True,
        )
        self.assertFalse(result_disallowed.can_encounter)
        self.assertIn("not permitted in area", result_disallowed.reason)

        # Disabled area
        self.forest_area.enabled = False
        result_disabled = self.encounter_mgr.check_encounter(
            player_position=player_pos,
            pokemon_position=pokemon_pos,
            pokemon=self.pikachu,
            area=self.forest_area,
            is_active=True,
        )
        self.assertFalse(result_disabled.can_encounter)
        self.assertIn("disabled", result_disabled.reason)

    # 13. A despawned Pokémon is no longer encounter-eligible through the area.
    def test_13_despawned_pokemon_is_no_longer_encounter_eligible(self) -> None:
        spawn_mgr = SpawnManager(
            spawn_configs=[PIKACHU_SPAWN_CONFIG],
            seed=42,
        )
        spawn_mgr.register_area(self.forest_area)

        # Spawn a wild Pikachu at (4.0, 4.0)
        wild_pika = spawn_mgr.attempt_spawn("forest", ignore_probability=True, position=(4.0, 4.0))
        self.assertIsNotNone(wild_pika)

        player_pos = (4.0, 5.0)  # 1.0m away, inside radius

        # Active check succeeds
        res_active = self.encounter_mgr.check_encounter_with_manager(
            spawn_manager=spawn_mgr,
            area_id="forest",
            player_position=player_pos,
            pokemon=wild_pika,
        )
        self.assertTrue(res_active.can_encounter)

        # Despawn the Pokemon
        spawn_mgr.despawn_pokemon("forest", wild_pika)
        self.assertFalse(spawn_mgr.is_pokemon_active("forest", wild_pika))

        # Check encounter again: rejected because no longer active!
        res_despawned = self.encounter_mgr.check_encounter(
            player_position=player_pos,
            pokemon_position=(4.0, 4.0),
            pokemon=wild_pika,
            area=self.forest_area,
            is_active=spawn_mgr.is_pokemon_active("forest", wild_pika),
        )
        self.assertFalse(res_despawned.can_encounter)
        self.assertIn("no longer active", res_despawned.reason)

    # Distance calculation tests
    def test_distance_calculation(self) -> None:
        # 2D distance
        d2 = self.encounter_mgr.calculate_distance((0.0, 0.0), (3.0, 4.0))
        self.assertAlmostEqual(d2, 5.0)

        # 3D distance
        d3 = self.encounter_mgr.calculate_distance((1.0, 2.0, 3.0), (4.0, 6.0, 3.0))
        self.assertAlmostEqual(d3, 5.0)

        # Dimension mismatch
        with self.assertRaises(ValueError):
            self.encounter_mgr.calculate_distance((1.0, 2.0), (1.0, 2.0, 3.0))


if __name__ == "__main__":
    unittest.main()
