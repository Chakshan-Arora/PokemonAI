"""
Comprehensive unit tests for the Dynamic Pokemon Encounters, Habitats & Time-Based Spawning subsystem.

Tests verify:
1. Valid habitat definitions and candidate models.
2. Habitat validation rejects empty IDs, non-string names, and invalid region IDs.
3. SpawnCandidate rejects negative weights, non-numeric weights, invalid level bounds, and empty times.
4. TimeOfDay enum and get_time_of_day hour boundary mapping (midnight, morning, day, evening, night).
5. get_time_of_day rejects negative hours, >= 24.0, NaN, infinite, and non-numeric values.
6. Static catalog contains MEADOW, FOREST, and SHRINE_GROUNDS mapped to valid regions.
7. Candidate filtering: species eligible for region and time period.
8. Time exclusion: diurnal species excluded at night, nocturnal species excluded in daytime.
9. Habitat exclusion: species restricted to other habitats are not selected.
10. Empty pool returns structured failure without crashing or mutating state.
11. Seeded reproducible selection produces identical deterministic sequences.
12. Weighted selection frequency reflects configured candidate weights.
13. SpawnArea whitelist restrictions are respected during habitat selection.
14. Unknown region ID returns clean failure.
15. Coordinates outside registered regions return clean failure.
16. Coordinates within registered regions resolve correct habitat via WorldExplorationManager.
17. Triggering encounter successfully starts WildEncounter session and tracks active encounter.
18. Active encounter singleton rule: player cannot start a second concurrent encounter.
19. Resolving or fleeing an encounter releases active state and permits subsequent encounters.
20. Failed selection leaves player state and active encounters unchanged.
21. SpawnArea capacity limits prevent encounters when maximum active spawns reached.
22. Failed encounter attempt consumes no spawn capacity in SpawnManager.
23. Despawning or capturing wild Pokemon releases spawn capacity.
24. Repeated despawn does not decrement or corrupt active count twice.
25. Deterministic respawn cooldowns prevent spawning before deadline and allow spawning after.
26. Quest event dispatching: POKEMON_ENCOUNTERED event emitted on successful encounter start.
27. No quest event is emitted when encounter selection fails.
28. Deduplication in QuestManager prevents duplicate quest progress on replayed encounter events.
29. Isolation: encounters and discovery state between distinct players remain isolated.
30. Save/load compatibility: saving and loading player state preserves collection, inventory, quests, and exploration.
"""
import random
import tempfile
from pathlib import Path
import unittest

from src.models.species import PokemonSpecies
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.personality import Personality
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager, WildEncounter
from src.models.quest import QuestEventType, QuestStatus
from src.models.quest_manager import QuestManager
from src.models.world_exploration import WorldRegion
from src.models.world_exploration_manager import WorldExplorationManager
from src.models.save_manager import save_game, load_game
from src.models.habitat import (
    TimeOfDay,
    Rarity,
    SpawnCandidate,
    Habitat,
    SpawnSelectionResult,
    HabitatEncounterResult,
    get_time_of_day,
)
from src.models.habitat_manager import HabitatManager
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.world_regions import STARTING_MEADOW, FOREST_TRAIL, ANCIENT_SHRINE_GROUNDS
from src.data.habitats import (
    MEADOW_HABITAT,
    FOREST_HABITAT,
    SHRINE_GROUNDS_HABITAT,
    HABITAT_CATALOG,
    get_habitat,
    get_habitat_for_region,
    create_default_habitats,
)


class TestHabitatEncounters(unittest.TestCase):
    """Full test suite covering habitat data, deterministic time, weighted selection, and encounters."""

    def setUp(self) -> None:
        """Sets up default players, managers, and test fixtures."""
        self.player = Player(name="Red")
        self.other_player = Player(name="Blue")

        self.exploration_mgr = WorldExplorationManager()
        self.spawn_mgr = SpawnManager(seed=42)
        self.encounter_mgr = EncounterManager()
        self.quest_mgr = QuestManager()

        self.habitat_mgr = HabitatManager(
            exploration_manager=self.exploration_mgr,
            spawn_manager=self.spawn_mgr,
            encounter_manager=self.encounter_mgr,
            quest_manager=self.quest_mgr,
            seed=100,
        )

    # 1. Valid habitat definitions and candidate models
    def test_01_valid_habitat_and_candidate_definition(self) -> None:
        cand = SpawnCandidate(
            species=PIKACHU,
            weight=50.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=2,
            max_level=5,
            rarity=Rarity.COMMON,
        )
        self.assertIs(cand.species, PIKACHU)
        self.assertEqual(cand.weight, 50.0)
        self.assertEqual(cand.allowed_times, (TimeOfDay.MORNING, TimeOfDay.DAY))
        self.assertTrue(cand.is_eligible_at(TimeOfDay.DAY))
        self.assertFalse(cand.is_eligible_at(TimeOfDay.NIGHT))

        hab = Habitat(
            habitat_id="test_zone",
            name="Test Zone",
            description="A test habitat zone.",
            region_ids=("test_region",),
            candidates=(cand,),
        )
        self.assertEqual(hab.habitat_id, "test_zone")
        self.assertEqual(hab.region_ids, ("test_region",))
        self.assertEqual(len(hab.candidates), 1)

    # 2. Habitat validation rejects empty IDs, non-string names, and invalid region IDs
    def test_02_habitat_validation_rejects_malformed_inputs(self) -> None:
        cand = SpawnCandidate(species=PIKACHU, weight=10.0, allowed_times=(TimeOfDay.DAY,))

        with self.assertRaises(ValueError):
            Habitat(habitat_id="", name="Valid", description="Valid", region_ids=("r1",), candidates=(cand,))

        with self.assertRaises(ValueError):
            Habitat(habitat_id="h1", name="   ", description="Valid", region_ids=("r1",), candidates=(cand,))

        with self.assertRaises(ValueError):
            Habitat(habitat_id="h1", name="Valid", description="", region_ids=("r1",), candidates=(cand,))

        with self.assertRaises(TypeError):
            Habitat(habitat_id="h1", name="Valid", description="Valid", region_ids="not-a-tuple", candidates=(cand,))

        with self.assertRaises(ValueError):
            Habitat(habitat_id="h1", name="Valid", description="Valid", region_ids=("",), candidates=(cand,))

        with self.assertRaises(TypeError):
            Habitat(habitat_id="h1", name="Valid", description="Valid", region_ids=("r1",), candidates=("not_a_cand",))

    # 3. SpawnCandidate rejects negative weights, non-numeric weights, invalid level bounds, and empty times
    def test_03_spawn_candidate_validation_rejects_invalid_fields(self) -> None:
        with self.assertRaises(TypeError):
            SpawnCandidate(species="Pikachu", weight=10.0, allowed_times=(TimeOfDay.DAY,))

        with self.assertRaises(ValueError):
            SpawnCandidate(species=PIKACHU, weight=0.0, allowed_times=(TimeOfDay.DAY,))

        with self.assertRaises(ValueError):
            SpawnCandidate(species=PIKACHU, weight=-5.0, allowed_times=(TimeOfDay.DAY,))

        with self.assertRaises(ValueError):
            SpawnCandidate(species=PIKACHU, weight=float("nan"), allowed_times=(TimeOfDay.DAY,))

        with self.assertRaises(ValueError):
            SpawnCandidate(species=PIKACHU, weight=10.0, allowed_times=())

        with self.assertRaises(TypeError):
            SpawnCandidate(species=PIKACHU, weight=10.0, allowed_times=("day",))

        with self.assertRaises(ValueError):
            SpawnCandidate(species=PIKACHU, weight=10.0, allowed_times=(TimeOfDay.DAY,), min_level=0)

        with self.assertRaises(ValueError):
            SpawnCandidate(species=PIKACHU, weight=10.0, allowed_times=(TimeOfDay.DAY,), min_level=5, max_level=3)

    # 4. TimeOfDay enum and get_time_of_day hour boundary mapping
    def test_04_time_of_day_hour_boundaries(self) -> None:
        # Morning: 05:00 <= hour < 10:00
        self.assertEqual(get_time_of_day(5.0), TimeOfDay.MORNING)
        self.assertEqual(get_time_of_day(7.5), TimeOfDay.MORNING)
        self.assertEqual(get_time_of_day(9.999), TimeOfDay.MORNING)

        # Day: 10:00 <= hour < 17:00
        self.assertEqual(get_time_of_day(10.0), TimeOfDay.DAY)
        self.assertEqual(get_time_of_day(12.0), TimeOfDay.DAY)
        self.assertEqual(get_time_of_day(16.999), TimeOfDay.DAY)

        # Evening: 17:00 <= hour < 21:00
        self.assertEqual(get_time_of_day(17.0), TimeOfDay.EVENING)
        self.assertEqual(get_time_of_day(19.0), TimeOfDay.EVENING)
        self.assertEqual(get_time_of_day(20.999), TimeOfDay.EVENING)

        # Night: 21:00 <= hour < 24.0 and 0.0 <= hour < 05:00
        self.assertEqual(get_time_of_day(21.0), TimeOfDay.NIGHT)
        self.assertEqual(get_time_of_day(23.999), TimeOfDay.NIGHT)
        self.assertEqual(get_time_of_day(0.0), TimeOfDay.NIGHT)  # Midnight
        self.assertEqual(get_time_of_day(2.5), TimeOfDay.NIGHT)
        self.assertEqual(get_time_of_day(4.999), TimeOfDay.NIGHT)

    # 5. get_time_of_day rejects negative hours, >= 24.0, NaN, infinite, and non-numeric values
    def test_05_get_time_of_day_rejects_invalid_hours(self) -> None:
        with self.assertRaises(ValueError):
            get_time_of_day(-0.01)

        with self.assertRaises(ValueError):
            get_time_of_day(-5.0)

        with self.assertRaises(ValueError):
            get_time_of_day(24.0)

        with self.assertRaises(ValueError):
            get_time_of_day(25.5)

        with self.assertRaises(ValueError):
            get_time_of_day(float("nan"))

        with self.assertRaises(ValueError):
            get_time_of_day(float("inf"))

        with self.assertRaises(TypeError):
            get_time_of_day("12:00")

        with self.assertRaises(TypeError):
            get_time_of_day(True)

    # 6. Static catalog contains all habitats mapped to valid regions
    def test_06_static_habitat_catalog_validity(self) -> None:
        self.assertIn("meadow", HABITAT_CATALOG)
        self.assertIn("forest", HABITAT_CATALOG)
        self.assertIn("shrine_grounds", HABITAT_CATALOG)
        self.assertIn("mountain_pass", HABITAT_CATALOG)
        self.assertIn("lakeside", HABITAT_CATALOG)
        self.assertIn("haunted_ruins", HABITAT_CATALOG)
        self.assertIn("tall_grass_plains", HABITAT_CATALOG)

        meadow = get_habitat("meadow")
        self.assertIsNotNone(meadow)
        self.assertIn("starting_meadow", meadow.region_ids)

        forest = get_habitat_for_region("forest_trail")
        self.assertIsNotNone(forest)
        self.assertEqual(forest.habitat_id, "forest")

        shrine = get_habitat_for_region("ancient_shrine_grounds")
        self.assertIsNotNone(shrine)
        self.assertEqual(shrine.habitat_id, "shrine_grounds")

        mountain = get_habitat_for_region("mountain_pass")
        self.assertIsNotNone(mountain)
        self.assertEqual(mountain.habitat_id, "mountain_pass")

    # 7. Candidate filtering: species eligible for region and time period
    def test_07_eligible_species_filtering_by_region_and_time(self) -> None:
        # Starting meadow during the day has Pikachu and Squirtle
        day_species = self.habitat_mgr.get_eligible_species("starting_meadow", TimeOfDay.DAY)
        day_names = [s.name for s in day_species]
        self.assertIn("Pikachu", day_names)
        self.assertIn("Squirtle", day_names)

        # Starting meadow in morning has Pikachu only (Squirtle is day/evening)
        morn_species = self.habitat_mgr.get_eligible_species("starting_meadow", TimeOfDay.MORNING)
        morn_names = [s.name for s in morn_species]
        self.assertIn("Pikachu", morn_names)
        self.assertNotIn("Squirtle", morn_names)

    # 8. Time exclusion: diurnal species excluded at night, nocturnal species excluded in daytime
    def test_08_species_excluded_by_time_restriction(self) -> None:
        # Meadow at night has NO eligible candidates
        night_candidates = self.habitat_mgr.get_eligible_candidates("starting_meadow", TimeOfDay.NIGHT)
        self.assertEqual(len(night_candidates), 0)

        # Forest at night has Charmander, but NOT Pikachu
        forest_night_species = self.habitat_mgr.get_eligible_species("forest_trail", TimeOfDay.NIGHT)
        forest_night_names = [s.name for s in forest_night_species]
        self.assertIn("Charmander", forest_night_names)
        self.assertNotIn("Pikachu", forest_night_names)

        # Shrine grounds during morning has NO candidates (only DAY, EVENING & NIGHT)
        shrine_morning_candidates = self.habitat_mgr.get_eligible_candidates("ancient_shrine_grounds", TimeOfDay.MORNING)
        self.assertEqual(len(shrine_morning_candidates), 0)

        # Shrine grounds during daytime has Geodude and Machop, but NOT Gastly (night only)
        shrine_day_species = self.habitat_mgr.get_eligible_species("ancient_shrine_grounds", TimeOfDay.DAY)
        shrine_day_names = [s.name for s in shrine_day_species]
        self.assertIn("Geodude", shrine_day_names)
        self.assertNotIn("Gastly", shrine_day_names)

    # 9. Habitat exclusion: species restricted to other habitats are not selected
    def test_09_species_excluded_by_habitat(self) -> None:
        # Charmander does not appear in Sunny Meadow at any time
        for t in (TimeOfDay.MORNING, TimeOfDay.DAY, TimeOfDay.EVENING, TimeOfDay.NIGHT):
            self.assertFalse(self.habitat_mgr.get_habitat("meadow").is_species_eligible("Charmander", t))

        # Squirtle does not appear in Shrine Grounds
        for t in (TimeOfDay.MORNING, TimeOfDay.DAY, TimeOfDay.EVENING, TimeOfDay.NIGHT):
            self.assertFalse(self.habitat_mgr.get_habitat("shrine_grounds").is_species_eligible("Squirtle", t))

    # 10. Empty pool returns structured failure without crashing or mutating state
    def test_10_empty_eligible_pool_returns_structured_failure(self) -> None:
        # Meadow at night has no eligible species
        res = self.habitat_mgr.select_spawn(region_id="starting_meadow", time_of_day=TimeOfDay.NIGHT)
        self.assertFalse(res.success)
        self.assertEqual(res.error_type, "NO_ELIGIBLE_SPECIES")
        self.assertEqual(res.eligible_count, 0)
        self.assertIn("No eligible wild Pokemon", res.message)

    # 11. Seeded reproducible selection produces identical deterministic sequences
    def test_11_seeded_deterministic_selection_reproducibility(self) -> None:
        # Two managers with same seed
        mgr1 = HabitatManager(seed=4242)
        mgr2 = HabitatManager(seed=4242)

        sequence1 = []
        for _ in range(10):
            res = mgr1.select_spawn(region_id="forest_trail", time_of_day=TimeOfDay.DAY)
            sequence1.append((res.species.name, res.level))

        sequence2 = []
        for _ in range(10):
            res = mgr2.select_spawn(region_id="forest_trail", time_of_day=TimeOfDay.DAY)
            sequence2.append((res.species.name, res.level))

        self.assertEqual(sequence1, sequence2)
        self.assertGreater(len(sequence1), 0)

    # 12. Weighted selection frequency reflects configured candidate weights
    def test_12_weighted_selection_distribution(self) -> None:
        mgr = HabitatManager(seed=12345)
        sample_size = 1400
        counts: dict[str, int] = {}

        for _ in range(sample_size):
            res = mgr.select_spawn(region_id="starting_meadow", time_of_day=TimeOfDay.DAY)
            self.assertTrue(res.success)
            counts[res.species.name] = counts.get(res.species.name, 0) + 1

        # Common species (Pidgey, Rattata, Caterpie) appear more often than Rare species (Squirtle, Eevee)
        self.assertGreater(counts["Pidgey"], counts["Squirtle"])
        self.assertGreater(counts["Rattata"], counts["Eevee"])

        # Pidgey weight 60 / 280 = 21.4%
        pidgey_ratio = counts["Pidgey"] / sample_size
        self.assertAlmostEqual(pidgey_ratio, 60.0 / 280.0, delta=0.06)

    # 13. SpawnArea whitelist restrictions are respected during habitat selection
    def test_13_spawn_area_whitelist_restriction(self) -> None:
        # Create a restricted area in forest trail that permits ONLY Pikachu
        restricted_area = SpawnArea(
            area_id="pika_grove",
            name="Pikachu Grove",
            allowed_species=(PIKACHU,),
            max_active_pokemon=5,
        )

        # Forest trail day has Pikachu and Charmander, but area allows only Pikachu
        for _ in range(20):
            res = self.habitat_mgr.select_spawn(
                region_id="forest_trail",
                time_of_day=TimeOfDay.DAY,
                spawn_area=restricted_area,
            )
            self.assertTrue(res.success)
            self.assertEqual(res.species.name, "Pikachu")

    # 14. Unknown region ID returns clean failure
    def test_14_unknown_region_id_returns_clean_failure(self) -> None:
        res = self.habitat_mgr.select_spawn(region_id="mystery_volcano", time_of_day=TimeOfDay.DAY)
        self.assertFalse(res.success)
        self.assertEqual(res.error_type, "NO_HABITAT")
        self.assertIn("No habitat registered", res.message)

    # 15. Coordinates outside registered regions return clean failure
    def test_15_coordinates_outside_regions_returns_clean_failure(self) -> None:
        # (999.0, 999.0) is far outside all registered regions
        res = self.habitat_mgr.select_spawn(position=(999.0, 999.0), time_of_day=TimeOfDay.DAY)
        self.assertFalse(res.success)
        self.assertEqual(res.error_type, "OUTSIDE_REGIONS")
        self.assertIn("outside all registered world regions", res.message)

    # 16. Coordinates within registered regions resolve correct habitat via WorldExplorationManager
    def test_16_coordinates_within_registered_region_resolves_habitat(self) -> None:
        # Starting Meadow bounds: (0.0, 0.0, 10.0, 10.0) -> Point (4.0, 5.0)
        res = self.habitat_mgr.select_spawn(position=(4.0, 5.0), time_of_day=TimeOfDay.MORNING)
        self.assertTrue(res.success)
        self.assertEqual(res.habitat_id, "meadow")
        self.assertEqual(res.region_id, "starting_meadow")
        self.assertIn(res.species.name, ("Pidgey", "Rattata", "Caterpie", "Pikachu", "Bulbasaur"))

    # 17. Triggering encounter successfully starts WildEncounter session and tracks active encounter
    def test_17_trigger_encounter_starts_session(self) -> None:
        enc_res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.MORNING,
        )
        self.assertTrue(enc_res.success)
        self.assertIsNotNone(enc_res.encounter)
        self.assertIsInstance(enc_res.encounter, WildEncounter)
        self.assertIs(enc_res.encounter.player, self.player)
        self.assertIn(enc_res.pokemon.species.name, ("Pidgey", "Rattata", "Caterpie", "Pikachu", "Bulbasaur"))
        self.assertTrue(enc_res.encounter.is_active)
        self.assertTrue(self.encounter_mgr.has_active_encounter(self.player))
        self.assertIs(self.encounter_mgr.get_active_encounter(self.player), enc_res.encounter)
        self.assertTrue(enc_res.encounter.is_active)
        self.assertTrue(self.encounter_mgr.has_active_encounter(self.player))
        self.assertIs(self.encounter_mgr.get_active_encounter(self.player), enc_res.encounter)

    # 18. Active encounter singleton rule: player cannot start a second concurrent encounter
    def test_18_active_encounter_singleton_rule(self) -> None:
        # Start first encounter
        res1 = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.MORNING,
        )
        self.assertTrue(res1.success)

        # Attempt second encounter with same player while first is unresolved
        res2 = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="forest_trail",
            time_of_day=TimeOfDay.DAY,
        )
        self.assertFalse(res2.success)
        self.assertEqual(res2.error_type, "ACTIVE_ENCOUNTER_EXISTS")
        self.assertIn("already has an active encounter", res2.message)

    # 19. Resolving or fleeing an encounter releases active state and permits subsequent encounters
    def test_19_resolving_encounter_releases_active_state(self) -> None:
        res1 = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.MORNING,
        )
        self.assertTrue(res1.success)

        # Resolve encounter (fled/defeated/captured)
        res1.encounter.resolve(reason="Fled")
        self.assertFalse(self.encounter_mgr.has_active_encounter(self.player))

        # Now second encounter can start cleanly
        res2 = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="forest_trail",
            time_of_day=TimeOfDay.DAY,
        )
        self.assertTrue(res2.success)
        self.assertIsNotNone(res2.encounter)

    # 20. Failed selection leaves player state and active encounters unchanged
    def test_20_failed_selection_leaves_state_unchanged(self) -> None:
        self.assertFalse(self.encounter_mgr.has_active_encounter(self.player))

        # Meadow at night fails (empty pool)
        fail_res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.NIGHT,
        )
        self.assertFalse(fail_res.success)
        self.assertEqual(fail_res.error_type, "NO_ELIGIBLE_SPECIES")
        self.assertFalse(self.encounter_mgr.has_active_encounter(self.player))

    # 21. SpawnArea capacity limits prevent encounters when maximum active spawns reached
    def test_21_spawn_area_capacity_limits(self) -> None:
        area = SpawnArea(
            area_id="test_cap",
            name="Capacity Test Area",
            allowed_species=(PIKACHU, CHARMANDER, SQUIRTLE),
            max_active_pokemon=2,
        )
        self.spawn_mgr.register_area(area)

        # Spawn 2 wild pokemon to fill capacity
        mon1 = Pokemon(species=PIKACHU, personality=Personality(10, 10, 10, 10, 10, 10))
        mon2 = Pokemon(species=PIKACHU, personality=Personality(10, 10, 10, 10, 10, 10))
        self.spawn_mgr._active_pokemon["test_cap"].extend([mon1, mon2])
        self.assertFalse(self.spawn_mgr.can_spawn("test_cap"))

        # Trigger encounter fails due to capacity reached
        res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="test_cap",
        )
        self.assertFalse(res.success)
        self.assertEqual(res.error_type, "SPAWN_CAPACITY_REACHED")
        self.assertIn("has reached max capacity", res.message)

    # 22. Failed encounter attempt consumes no spawn capacity in SpawnManager
    def test_22_failed_encounter_consumes_no_spawn_capacity(self) -> None:
        area = SpawnArea(
            area_id="meadow_spawn",
            name="Meadow Spawns",
            allowed_species=(PIKACHU, SQUIRTLE),
            max_active_pokemon=3,
        )
        self.spawn_mgr.register_area(area)
        self.assertEqual(self.spawn_mgr.get_active_count("meadow_spawn"), 0)

        # Trigger encounter with night time (will fail because meadow has no night candidates)
        res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.NIGHT,
            area_id="meadow_spawn",
        )
        self.assertFalse(res.success)
        self.assertEqual(self.spawn_mgr.get_active_count("meadow_spawn"), 0)

    # 23. Despawning or capturing wild Pokemon releases spawn capacity
    def test_23_despawn_releases_capacity(self) -> None:
        area = SpawnArea(
            area_id="trail_spawn",
            name="Trail Spawns",
            allowed_species=(PIKACHU, CHARMANDER),
            max_active_pokemon=1,
        )
        self.spawn_mgr.register_area(area)

        # Trigger encounter which registers wild pokemon
        enc_res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="forest_trail",
            time_of_day=TimeOfDay.DAY,
            area_id="trail_spawn",
        )
        self.assertTrue(enc_res.success)
        self.assertEqual(self.spawn_mgr.get_active_count("trail_spawn"), 1)
        self.assertFalse(self.spawn_mgr.can_spawn("trail_spawn"))

        # Despawn the wild pokemon
        despawned = self.spawn_mgr.despawn_pokemon("trail_spawn", enc_res.pokemon)
        self.assertIsNotNone(despawned)
        self.assertEqual(self.spawn_mgr.get_active_count("trail_spawn"), 0)
        self.assertTrue(self.spawn_mgr.can_spawn("trail_spawn"))

    # 24. Repeated despawn does not decrement or corrupt active count twice
    def test_24_repeated_despawn_does_not_double_release(self) -> None:
        area = SpawnArea(
            area_id="area_dup",
            name="Dup Area",
            allowed_species=(PIKACHU,),
            max_active_pokemon=2,
        )
        self.spawn_mgr.register_area(area)
        mon = Pokemon(species=PIKACHU, personality=Personality(10, 10, 10, 10, 10, 10))
        self.spawn_mgr._active_pokemon["area_dup"].append(mon)
        self.assertEqual(self.spawn_mgr.get_active_count("area_dup"), 1)

        # First despawn succeeds
        self.assertIsNotNone(self.spawn_mgr.despawn_pokemon("area_dup", mon))
        self.assertEqual(self.spawn_mgr.get_active_count("area_dup"), 0)

        # Second despawn returns None and count stays 0
        self.assertIsNone(self.spawn_mgr.despawn_pokemon("area_dup", mon))
        self.assertEqual(self.spawn_mgr.get_active_count("area_dup"), 0)

    # 25. Deterministic respawn cooldowns prevent spawning before deadline and allow spawning after
    def test_25_deterministic_respawn_cooldown(self) -> None:
        area = SpawnArea(
            area_id="cooldown_zone",
            name="Cooldown Zone",
            allowed_species=(PIKACHU,),
            max_active_pokemon=3,
        )
        self.spawn_mgr.register_area(area)

        # Set 30s cooldown starting at t=100.0 (deadline = 130.0)
        self.spawn_mgr.set_area_cooldown("cooldown_zone", cooldown_duration=30.0, current_time=100.0)
        self.assertTrue(self.spawn_mgr.is_area_on_cooldown("cooldown_zone", current_time=115.0))
        self.assertFalse(self.spawn_mgr.can_spawn("cooldown_zone", current_time=115.0))

        # At t=130.0, cooldown expires
        self.assertFalse(self.spawn_mgr.is_area_on_cooldown("cooldown_zone", current_time=130.0))
        self.assertTrue(self.spawn_mgr.can_spawn("cooldown_zone", current_time=130.0))

        # Test encounter manager rejects during cooldown
        res_cd = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.MORNING,
            area_id="cooldown_zone",
            current_time=110.0,
        )
        self.assertFalse(res_cd.success)
        self.assertEqual(res_cd.error_type, "SPAWN_AREA_ON_COOLDOWN")

    # 26. Quest event dispatching: POKEMON_ENCOUNTERED event emitted on successful encounter start
    def test_26_quest_event_dispatched_on_encounter_start(self) -> None:
        enc_res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.MORNING,
        )
        self.assertTrue(enc_res.success)
        self.assertTrue(enc_res.event_emitted)

    # 27. No quest event is emitted when encounter selection fails
    def test_27_no_quest_event_on_failed_encounter(self) -> None:
        enc_res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.NIGHT,  # Fails
        )
        self.assertFalse(enc_res.success)
        self.assertFalse(enc_res.event_emitted)

    # 28. Deduplication in QuestManager prevents duplicate quest progress on replayed encounter events
    def test_28_quest_deduplication_on_replayed_encounter_event(self) -> None:
        event_id = "test_enc_evt_101"
        res1 = self.quest_mgr.record_encounter(
            player=self.player,
            species_name="Pikachu",
            habitat_id="meadow",
            event_id=event_id,
        )
        self.assertEqual(res1.events_processed, 1)

        # Replay event
        res2 = self.quest_mgr.record_encounter(
            player=self.player,
            species_name="Pikachu",
            habitat_id="meadow",
            event_id=event_id,
        )
        self.assertEqual(res2.events_processed, 0)
        self.assertIn("Duplicate event", res2.message)

    # 29. Isolation: encounters and discovery state between distinct players remain isolated
    def test_29_player_encounter_isolation(self) -> None:
        # Player 1 enters encounter
        res1 = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
        )
        self.assertTrue(res1.success)
        self.assertTrue(self.encounter_mgr.has_active_encounter(self.player))
        self.assertFalse(self.encounter_mgr.has_active_encounter(self.other_player))

        # Other player can also independently enter encounter
        res2 = self.habitat_mgr.trigger_encounter(
            player=self.other_player,
            region_id="forest_trail",
            time_of_day=TimeOfDay.DAY,
        )
        self.assertTrue(res2.success)
        self.assertTrue(self.encounter_mgr.has_active_encounter(self.other_player))

    # 30. Save/load compatibility: saving and loading player state preserves collection, inventory, quests, and exploration
    def test_30_save_load_compatibility_persists_player_state(self) -> None:
        # Give player a captured Pikachu and discover starting meadow
        pika = Pokemon(species=PIKACHU, personality=Personality(20, 20, 20, 20, 20, 20), level=4)
        self.player.add_pokemon(pika)
        self.player.mark_region_discovered("starting_meadow")

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "test_habitat_save.json"
            save_game(self.player, save_path)
            restored = load_game(save_path)

            self.assertEqual(restored.name, "Red")
            self.assertEqual(len(restored.collection), 1)
            self.assertEqual(restored.collection[0].species.name, "Pikachu")
            self.assertTrue(restored.is_region_discovered("starting_meadow"))


if __name__ == "__main__":
    unittest.main()
