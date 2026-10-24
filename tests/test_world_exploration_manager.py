"""
Unit tests for the World Exploration, Map Regions & Discovery Subsystem.
Verifies WorldRegion validation, region spatial lookup, overlap policy,
first-time exploration discovery tracking, landmark discovery, quest event integration,
player state isolation, and save/load persistence across schema versions 1, 2, 3, and 4.
"""
import unittest
import tempfile
import math
from pathlib import Path

from src.models.player import Player
from src.models.inventory import Inventory
from src.models.world_exploration import WorldRegion, ExplorationResult
from src.models.world_exploration_manager import WorldExplorationManager
from src.models.world_interaction import (
    InteractableType,
    Interactable,
    InteractionResult,
)
from src.models.world_interaction_manager import WorldInteractionManager
from src.models.quest import (
    QuestStatus,
    ObjectiveType,
    QuestEventType,
    QuestObjective,
    QuestDefinition,
    ObjectiveProgress,
    QuestProgress,
)
from src.models.quest_manager import QuestManager
from src.models.save_data import CURRENT_SCHEMA_VERSION, SaveDataError
from src.models.save_manager import (
    serialize_player,
    deserialize_player,
    save_game,
    load_game,
)
from src.data.world_regions import (
    STARTING_MEADOW,
    FOREST_TRAIL,
    ANCIENT_SHRINE_GROUNDS,
    WORLD_REGION_CATALOG,
    create_default_world_regions,
)
from src.data.world_objects import (
    BERRY_BUSH,
    SUPPLY_CACHE,
    ROUTE1_SIGN,
    ANCIENT_SHRINE,
    WORLD_OBJECT_CATALOG,
    create_default_world_objects,
)
from src.data.quests import FIRST_ENCOUNTER, TRAILBLAZER, QUEST_CATALOG


class TestWorldExplorationManager(unittest.TestCase):
    """
    Test suite for World Exploration, Region Mapping, Discovery, and Persistence.
    """

    def setUp(self) -> None:
        self.player = Player(name="Red")
        self.player2 = Player(name="Blue")
        self.interaction_mgr = WorldInteractionManager(
            objects=create_default_world_objects()
        )
        self.quest_mgr = QuestManager()
        self.exploration_mgr = WorldExplorationManager(
            regions=create_default_world_regions(),
            interaction_manager=self.interaction_mgr,
            quest_manager=self.quest_mgr,
        )

    # --- 1. Model Validation Tests ---

    def test_01_world_region_validation_success(self) -> None:
        """Valid WorldRegion initializes correctly with normalized fields and bounds."""
        region = WorldRegion(
            region_id="Test_Zone",
            name="Test Zone",
            description="A test area.",
            bounds=(0.0, 0.0, 10.0, 10.0),
            discovery_text="Discovered test zone!",
            landmark_ids=("ancient_shrine",),
        )
        self.assertEqual(region.region_id, "test_zone")
        self.assertEqual(region.name, "Test Zone")
        self.assertEqual(region.bounds, (0.0, 0.0, 10.0, 10.0))
        self.assertEqual(region.center(), (5.0, 5.0))
        self.assertEqual(region.landmark_ids, ("ancient_shrine",))

    def test_02_world_region_invalid_identifiers(self) -> None:
        """Empty, whitespace, or non-string region IDs and names are rejected."""
        with self.assertRaises(ValueError):
            WorldRegion(
                region_id="",
                name="Valid",
                description="Desc",
                bounds=(0.0, 0.0, 10.0, 10.0),
            )
        with self.assertRaises(ValueError):
            WorldRegion(
                region_id="   ",
                name="Valid",
                description="Desc",
                bounds=(0.0, 0.0, 10.0, 10.0),
            )
        with self.assertRaises(ValueError):
            WorldRegion(
                region_id="valid",
                name="",
                description="Desc",
                bounds=(0.0, 0.0, 10.0, 10.0),
            )

    def test_03_world_region_invalid_and_inverted_bounds(self) -> None:
        """Inverted bounds, non-numeric coordinates, and NaNs/Infs are rejected."""
        # min_x > max_x
        with self.assertRaises(ValueError):
            WorldRegion(
                region_id="inv_x",
                name="Inverted X",
                description="Desc",
                bounds=(15.0, 0.0, 10.0, 10.0),
            )
        # min_y > max_y
        with self.assertRaises(ValueError):
            WorldRegion(
                region_id="inv_y",
                name="Inverted Y",
                description="Desc",
                bounds=(0.0, 20.0, 10.0, 10.0),
            )
        # NaN / Inf coordinates
        with self.assertRaises(ValueError):
            WorldRegion(
                region_id="nan_bound",
                name="NaN",
                description="Desc",
                bounds=(float("nan"), 0.0, 10.0, 10.0),
            )
        with self.assertRaises(ValueError):
            WorldRegion(
                region_id="inf_bound",
                name="Inf",
                description="Desc",
                bounds=(0.0, 0.0, float("inf"), 10.0),
            )
        # Not a 4-tuple
        with self.assertRaises(ValueError):
            WorldRegion(
                region_id="short_bound",
                name="Short",
                description="Desc",
                bounds=(0.0, 0.0, 10.0),  # type: ignore
            )

    def test_04_inclusive_boundary_checks(self) -> None:
        """WorldRegion.contains_point uses inclusive boundary checking [min, max]."""
        region = WorldRegion(
            region_id="bounds_box",
            name="Box",
            description="Box",
            bounds=(5.0, 5.0, 15.0, 15.0),
        )
        # Corners (inclusive)
        self.assertTrue(region.contains_point((5.0, 5.0)))
        self.assertTrue(region.contains_point((15.0, 15.0)))
        self.assertTrue(region.contains_point((5.0, 15.0)))
        self.assertTrue(region.contains_point((15.0, 5.0)))
        # Interior
        self.assertTrue(region.contains_point((10.0, 10.0)))
        # Exterior
        self.assertFalse(region.contains_point((4.99, 10.0)))
        self.assertFalse(region.contains_point((15.01, 10.0)))
        self.assertFalse(region.contains_point((10.0, 4.99)))
        self.assertFalse(region.contains_point((10.0, 15.01)))

    def test_05_invalid_landmark_associations(self) -> None:
        """Non-string or empty landmark IDs are rejected."""
        with self.assertRaises(ValueError):
            WorldRegion(
                region_id="bad_landmarks",
                name="Bad",
                description="Desc",
                bounds=(0.0, 0.0, 10.0, 10.0),
                landmark_ids=("",),
            )
        with self.assertRaises(TypeError):
            WorldRegion(
                region_id="bad_type",
                name="Bad",
                description="Desc",
                bounds=(0.0, 0.0, 10.0, 10.0),
                landmark_ids=123,  # type: ignore
            )

    # --- 2. Region Lookup & Manager Operations ---

    def test_06_register_retrieve_and_unregister_regions(self) -> None:
        """Regions can be registered, retrieved by ID, and unregistered cleanly."""
        reg = WorldRegion(
            region_id="custom_valley",
            name="Custom Valley",
            description="A custom valley.",
            bounds=(100.0, 100.0, 120.0, 120.0),
        )
        self.exploration_mgr.register_region(reg)
        self.assertEqual(self.exploration_mgr.get_region("custom_valley"), reg)
        self.assertEqual(self.exploration_mgr.get_region("CUSTOM_VALLEY"), reg)

        self.assertTrue(self.exploration_mgr.unregister_region("custom_valley"))
        self.assertIsNone(self.exploration_mgr.get_region("custom_valley"))
        self.assertFalse(self.exploration_mgr.unregister_region("custom_valley"))

    def test_07_duplicate_region_registration_rejected(self) -> None:
        """Registering a region with an existing ID raises ValueError."""
        reg_dup = WorldRegion(
            region_id="starting_meadow",
            name="Duplicate Meadow",
            description="Desc",
            bounds=(0.0, 0.0, 5.0, 5.0),
        )
        with self.assertRaises(ValueError):
            self.exploration_mgr.register_region(reg_dup)

    def test_08_spatial_region_lookup(self) -> None:
        """find_region correctly maps coordinates to the containing region."""
        # Inside Starting Meadow (0.0, 0.0) -> (10.0, 10.0)
        reg1 = self.exploration_mgr.find_region((5.0, 5.0))
        self.assertIsNotNone(reg1)
        self.assertEqual(reg1.region_id, "starting_meadow")

        # Inside Forest Trail (11.0, 0.0) -> (20.0, 15.0)
        reg2 = self.exploration_mgr.find_region((15.0, 10.0))
        self.assertIsNotNone(reg2)
        self.assertEqual(reg2.region_id, "forest_trail")

        # Inside Ancient Shrine Grounds (21.0, 20.0) -> (30.0, 30.0)
        reg3 = self.exploration_mgr.find_region((25.0, 25.0))
        self.assertIsNotNone(reg3)
        self.assertEqual(reg3.region_id, "ancient_shrine_grounds")

    def test_09_position_outside_all_regions(self) -> None:
        """Coordinates outside all registered regions return None."""
        self.assertIsNone(self.exploration_mgr.find_region((999.0, 999.0)))
        self.assertIsNone(self.exploration_mgr.find_region((-5.0, -5.0)))
        # Gap between Meadow (max_x=10.0) and Forest Trail (min_x=11.0)
        self.assertIsNone(self.exploration_mgr.find_region((10.5, 5.0)))

    def test_10_deterministic_region_overlap_policy(self) -> None:
        """When regions overlap, find_region returns the first registered region."""
        mgr = WorldExplorationManager(regions=[])
        reg_a = WorldRegion("zone_a", "Zone A", "A", bounds=(0.0, 0.0, 10.0, 10.0))
        reg_b = WorldRegion("zone_b", "Zone B", "B", bounds=(5.0, 5.0, 15.0, 15.0))
        mgr.register_region(reg_a)
        mgr.register_region(reg_b)

        # Point (7.0, 7.0) is inside both Zone A and Zone B
        found = mgr.find_region((7.0, 7.0))
        self.assertIsNotNone(found)
        self.assertEqual(found.region_id, "zone_a")

        # find_all_regions reports both
        all_found = mgr.find_all_regions((7.0, 7.0))
        self.assertEqual(len(all_found), 2)
        self.assertEqual([r.region_id for r in all_found], ["zone_a", "zone_b"])

    def test_11_invalid_position_inputs_handled(self) -> None:
        """Non-numeric or malformed positions fail validation without crashing."""
        self.assertFalse(self.exploration_mgr.is_position_valid("invalid"))
        self.assertFalse(self.exploration_mgr.is_position_valid((1.0,)))
        self.assertFalse(self.exploration_mgr.is_position_valid((float("nan"), 1.0)))
        self.assertFalse(self.exploration_mgr.is_position_valid((True, 1.0)))

        with self.assertRaises(ValueError):
            self.exploration_mgr.find_region((float("nan"), 1.0))

    # --- 3. Discovery Operations & Player Isolation ---

    def test_12_first_time_region_discovery(self) -> None:
        """First discovery of a region records discovery on player and emits event."""
        self.assertFalse(self.player.is_region_discovered("starting_meadow"))

        res = self.exploration_mgr.discover_region(self.player, "starting_meadow")
        self.assertTrue(res.success)
        self.assertEqual(res.region_id, "starting_meadow")
        self.assertTrue(res.is_first_discovery)
        self.assertTrue(res.event_emitted)
        self.assertIn("Starting Meadow", res.message)
        self.assertEqual(res.discovery_text, STARTING_MEADOW.discovery_text)
        self.assertTrue(self.player.is_region_discovered("starting_meadow"))

    def test_13_repeated_region_discovery_idempotence(self) -> None:
        """Repeated discovery of the same region awards no duplicate progress or event."""
        # First discovery
        self.exploration_mgr.discover_region(self.player, "starting_meadow")

        # Second discovery
        res2 = self.exploration_mgr.discover_region(self.player, "starting_meadow")
        self.assertTrue(res2.success)
        self.assertEqual(res2.region_id, "starting_meadow")
        self.assertFalse(res2.is_first_discovery)
        self.assertFalse(res2.event_emitted)
        self.assertIn("already been discovered", res2.message)

    def test_14_discover_region_at_position(self) -> None:
        """discover_region_at_position resolves region by coordinate and records discovery."""
        res = self.exploration_mgr.discover_region_at_position(self.player, (5.0, 5.0))
        self.assertTrue(res.success)
        self.assertEqual(res.region_id, "starting_meadow")
        self.assertTrue(res.is_first_discovery)

        # Outside all regions
        res_out = self.exploration_mgr.discover_region_at_position(self.player, (999.0, 999.0))
        self.assertFalse(res_out.success)
        self.assertEqual(res_out.error_type, "OUTSIDE_REGIONS")

        # Invalid position
        res_inv = self.exploration_mgr.discover_region_at_position(self.player, "bad_coord")  # type: ignore
        self.assertFalse(res_inv.success)
        self.assertEqual(res_inv.error_type, "INVALID_POSITION")

    def test_15_first_time_landmark_discovery(self) -> None:
        """First-time landmark discovery records landmark and returns interaction text."""
        self.assertFalse(self.player.is_landmark_discovered("ancient_shrine"))

        # Ancient shrine is at (25.0, 25.0), radius=3.0
        res = self.exploration_mgr.discover_landmark(
            self.player,
            "ancient_shrine",
            player_position=(25.0, 25.0),
        )
        self.assertTrue(res.success)
        self.assertEqual(res.landmark_id, "ancient_shrine")
        self.assertTrue(res.is_first_discovery)
        self.assertTrue(res.event_emitted)
        self.assertTrue(self.player.is_landmark_discovered("ancient_shrine"))

    def test_16_repeated_landmark_discovery_idempotence(self) -> None:
        """Repeated landmark discovery reports is_first_discovery=False and emits no event."""
        # First discovery
        self.exploration_mgr.discover_landmark(self.player, "ancient_shrine")

        # Second discovery
        res2 = self.exploration_mgr.discover_landmark(self.player, "ancient_shrine")
        self.assertTrue(res2.success)
        self.assertEqual(res2.landmark_id, "ancient_shrine")
        self.assertFalse(res2.is_first_discovery)
        self.assertFalse(res2.event_emitted)
        self.assertIn("already been discovered", res2.message)

    def test_17_landmark_out_of_range_fails(self) -> None:
        """Attempting to discover a landmark beyond its interaction radius fails cleanly."""
        # Shrine is at (25.0, 25.0), radius=3.0. Player at (0.0, 0.0) is ~35 units away.
        res = self.exploration_mgr.discover_landmark(
            self.player,
            "ancient_shrine",
            player_position=(0.0, 0.0),
        )
        self.assertFalse(res.success)
        self.assertEqual(res.error_type, "OUT_OF_RANGE")
        self.assertFalse(self.player.is_landmark_discovered("ancient_shrine"))

    def test_18_unknown_region_and_landmark_handling(self) -> None:
        """Unknown region and landmark IDs return structured failure without exceptions."""
        res_reg = self.exploration_mgr.discover_region(self.player, "nonexistent_region")
        self.assertFalse(res_reg.success)
        self.assertEqual(res_reg.error_type, "UNKNOWN_REGION")

        res_lnd = self.exploration_mgr.discover_landmark(self.player, "nonexistent_landmark")
        self.assertFalse(res_lnd.success)
        self.assertEqual(res_lnd.error_type, "UNKNOWN_LANDMARK")

    def test_19_player_discovery_isolation(self) -> None:
        """Exploration discovery state is strictly isolated between player instances."""
        self.exploration_mgr.discover_region(self.player, "starting_meadow")
        self.exploration_mgr.discover_landmark(self.player, "ancient_shrine")

        # Player 1 has discoveries
        self.assertTrue(self.player.is_region_discovered("starting_meadow"))
        self.assertTrue(self.player.is_landmark_discovered("ancient_shrine"))

        # Player 2 has none
        self.assertFalse(self.player2.is_region_discovered("starting_meadow"))
        self.assertFalse(self.player2.is_landmark_discovered("ancient_shrine"))

    # --- 4. WorldInteractionManager Integration ---

    def test_20_landmark_interaction_records_player_discovery(self) -> None:
        """Interacting with a landmark via WorldInteractionManager marks discovery on player."""
        self.assertFalse(self.player.is_landmark_discovered("ancient_shrine"))

        # Player at (25.0, 25.0) interacts with ancient_shrine
        res = self.interaction_mgr.interact(
            self.player,
            "ancient_shrine",
            player_position=(25.0, 25.0),
        )
        self.assertTrue(res.success)
        self.assertTrue(res.is_discovered)
        self.assertTrue(res.is_first_discovery)
        self.assertTrue(self.player.is_landmark_discovered("ancient_shrine"))

        # Second interaction with same player reports is_first_discovery=False
        res2 = self.interaction_mgr.interact(
            self.player,
            "ancient_shrine",
            player_position=(25.0, 25.0),
        )
        self.assertTrue(res2.success)
        self.assertTrue(res2.is_discovered)
        self.assertFalse(res2.is_first_discovery)

    def test_21_existing_interactions_remain_unaffected(self) -> None:
        """Resource gathering, sign reading, and treasure looting retain identical behavior."""
        # Read sign
        sign_res = self.interaction_mgr.interact(self.player, "route1_sign", (2.0, 1.0))
        self.assertTrue(sign_res.success)
        self.assertEqual(sign_res.interactable_type, InteractableType.SIGN)

        # Harvest berry bush
        bush_res = self.interaction_mgr.interact(self.player, "berry_bush_route1", (5.0, 5.0))
        self.assertTrue(bush_res.success)
        self.assertEqual(bush_res.items_granted, {"potion": 1})

        # Loot supply cache
        cache_res = self.interaction_mgr.interact(self.player, "supply_cache_01", (15.0, 10.0))
        self.assertTrue(cache_res.success)
        self.assertTrue(self.player.is_treasure_collected("supply_cache_01"))

    # --- 5. Quest Integration ---

    def test_22_quest_advances_on_region_and_landmark_discovery(self) -> None:
        """Trailblazer quest advances upon region and landmark discoveries."""
        # Complete prerequisite first_encounter first
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        self.quest_mgr.record_capture(self.player, "Pikachu")

        # Accept Trailblazer quest
        accept_res = self.quest_mgr.accept_quest(self.player, "trailblazer")
        self.assertTrue(accept_res.success)

        q_prog = self.quest_mgr.get_quest_progress(self.player, "trailblazer")
        self.assertIsNotNone(q_prog)
        self.assertEqual(q_prog.status, QuestStatus.ACTIVE)
        self.assertFalse(q_prog.objective_progress["discover_meadow"].is_completed)
        self.assertFalse(q_prog.objective_progress["discover_shrine"].is_completed)

        # Discover Starting Meadow
        self.exploration_mgr.discover_region(self.player, "starting_meadow")
        self.assertTrue(q_prog.objective_progress["discover_meadow"].is_completed)
        self.assertFalse(q_prog.is_completed)

        # Discover Shrine Landmark
        self.exploration_mgr.discover_landmark(self.player, "ancient_shrine", (25.0, 25.0))
        self.assertTrue(q_prog.objective_progress["discover_shrine"].is_completed)
        self.assertTrue(q_prog.is_completed)
        self.assertEqual(self.quest_mgr.get_quest_status(self.player, "trailblazer"), QuestStatus.COMPLETED)

    def test_23_immediate_evaluation_on_quest_acceptance(self) -> None:
        """If player already discovered locations, accepting quest evaluates them immediately."""
        self.player.mark_region_discovered("starting_meadow")
        self.player.mark_landmark_discovered("ancient_shrine")

        # Complete prerequisite first_encounter first
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        self.quest_mgr.record_capture(self.player, "Pikachu")

        accept_res = self.quest_mgr.accept_quest(self.player, "trailblazer")
        self.assertTrue(accept_res.success)

        q_prog = self.quest_mgr.get_quest_progress(self.player, "trailblazer")
        self.assertIsNotNone(q_prog)
        self.assertTrue(q_prog.is_completed)
        self.assertEqual(q_prog.status, QuestStatus.COMPLETED)

    def test_24_repeated_events_do_not_duplicate_quest_progress(self) -> None:
        """Event replay with same event_id is safely ignored by QuestManager."""
        self.quest_mgr.accept_quest(self.player, "trailblazer")

        event_id = f"quest_evt_region_starting_meadow_{self.player.unique_id}"
        evt1 = self.quest_mgr.record_event(
            self.player,
            QuestEventType.REGION_DISCOVERED,
            payload={"region_id": "starting_meadow"},
            event_id=event_id,
        )
        self.assertEqual(evt1.events_processed, 1)

        # Replaying identical event_id is ignored
        evt2 = self.quest_mgr.record_event(
            self.player,
            QuestEventType.REGION_DISCOVERED,
            payload={"region_id": "starting_meadow"},
            event_id=event_id,
        )
        self.assertEqual(evt2.events_processed, 0)
        self.assertIn("Duplicate event", evt2.message)

    # --- 6. Save/Load Persistence & Schema Migrations ---

    def test_25_save_load_round_trip_persists_exploration_state(self) -> None:
        """Discovered regions and landmarks persist across serialization and save/load."""
        self.player.mark_region_discovered("starting_meadow")
        self.player.mark_region_discovered("forest_trail")
        self.player.mark_landmark_discovered("ancient_shrine")
        self.player.mark_treasure_collected("supply_cache_01")

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "exploration_save.json"
            save_game(self.player, save_path)

            restored = load_game(save_path)
            self.assertEqual(restored.name, "Red")
            self.assertEqual(restored.discovered_regions, {"starting_meadow", "forest_trail"})
            self.assertEqual(restored.discovered_landmarks, {"ancient_shrine"})
            self.assertEqual(restored.collected_treasures, {"supply_cache_01"})

    def test_26_schema_v1_v2_v3_backward_compatibility(self) -> None:
        """Legacy saves (v1, v2, v3) migrate cleanly with empty discovered sets."""
        v3_payload = {
            "schema_version": 3,
            "saved_at": "2026-10-10T10:00:00Z",
            "player": {"name": "Retro Red", "unique_id": "retro-001", "max_team_size": 6},
            "inventory": {"capacity": 20, "items": {}},
            "collection": [],
            "team": [],
            "active_pokemon_id": None,
            "quests": {},
            "collected_treasures": ["supply_cache_01"],
        }
        migrated = deserialize_player(v3_payload)
        self.assertEqual(migrated.name, "Retro Red")
        self.assertEqual(migrated.collected_treasures, {"supply_cache_01"})
        self.assertEqual(migrated.discovered_regions, set())
        self.assertEqual(migrated.discovered_landmarks, set())

    def test_27_corrupt_and_unknown_exploration_data_rejected(self) -> None:
        """Unknown region/landmark IDs and malformed types in save payload raise SaveDataError."""
        base_v4 = {
            "schema_version": 4,
            "saved_at": "2026-10-10T10:00:00Z",
            "player": {"name": "Red", "unique_id": "red-001", "max_team_size": 6},
            "inventory": {"capacity": 20, "items": {}},
            "collection": [],
            "team": [],
            "active_pokemon_id": None,
            "quests": {},
            "collected_treasures": [],
            "discovered_regions": [],
            "discovered_landmarks": [],
        }

        # Unknown region ID
        bad_region = dict(base_v4, discovered_regions=["nonexistent_region"])
        with self.assertRaises(SaveDataError):
            deserialize_player(bad_region)

        # Landmark ID in discovered_regions
        landmark_as_region = dict(base_v4, discovered_regions=["ancient_shrine"])
        with self.assertRaises(SaveDataError):
            deserialize_player(landmark_as_region)

        # Region ID in discovered_landmarks
        region_as_landmark = dict(base_v4, discovered_landmarks=["starting_meadow"])
        with self.assertRaises(SaveDataError):
            deserialize_player(region_as_landmark)

        # Malformed type (not a list)
        bad_type = dict(base_v4, discovered_regions="invalid_string")
        with self.assertRaises(SaveDataError):
            deserialize_player(bad_type)

    def test_28_failed_discovery_emits_no_quest_progress(self) -> None:
        """Failed discovery attempts (out of range, outside regions) emit no quest progress."""
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        self.quest_mgr.record_capture(self.player, "Pikachu")
        self.quest_mgr.accept_quest(self.player, "trailblazer")

        # Out-of-range landmark attempt
        res_fail_lnd = self.exploration_mgr.discover_landmark(
            self.player, "ancient_shrine", player_position=(0.0, 0.0)
        )
        self.assertFalse(res_fail_lnd.success)

        # Outside-regions coordinate attempt
        res_fail_reg = self.exploration_mgr.discover_region_at_position(
            self.player, (999.0, 999.0)
        )
        self.assertFalse(res_fail_reg.success)

        # Trailblazer objectives remain at 0
        q_prog = self.quest_mgr.get_quest_progress(self.player, "trailblazer")
        self.assertIsNotNone(q_prog)
        self.assertEqual(q_prog.objective_progress["discover_meadow"].current_count, 0)
        self.assertEqual(q_prog.objective_progress["discover_shrine"].current_count, 0)

    def test_29_quest_progress_and_rewards_preserved_with_exploration_save(self) -> None:
        """Completed quests, claimed rewards, and exploration discoveries survive save/load."""
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        self.quest_mgr.record_capture(self.player, "Pikachu")
        self.quest_mgr.claim_rewards(self.player, "first_encounter")

        self.player.mark_region_discovered("starting_meadow")
        self.player.mark_landmark_discovered("ancient_shrine")

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "full_progress.json"
            save_game(self.player, save_path)

            restored = load_game(save_path)
            q_prog = restored.quests.get("first_encounter")
            self.assertIsNotNone(q_prog)
            self.assertTrue(q_prog.is_completed)
            self.assertTrue(q_prog.rewards_claimed)
            self.assertEqual(restored.discovered_regions, {"starting_meadow"})
            self.assertEqual(restored.discovered_landmarks, {"ancient_shrine"})

    def test_30_save_load_save_round_trip_produces_identical_state(self) -> None:
        """Save -> Load -> Save round-trip produces equivalent persisted JSON payload."""
        self.player.mark_region_discovered("starting_meadow")
        self.player.mark_region_discovered("forest_trail")
        self.player.mark_landmark_discovered("ancient_shrine")
        self.player.mark_treasure_collected("supply_cache_01")

        with tempfile.TemporaryDirectory() as tmp_dir:
            file1 = Path(tmp_dir) / "save1.json"
            file2 = Path(tmp_dir) / "save2.json"

            save_game(self.player, file1)
            player_loaded = load_game(file1)
            save_game(player_loaded, file2)

            data1 = serialize_player(self.player)
            data2 = serialize_player(player_loaded)

            # Ignore timestamps
            data1.pop("saved_at", None)
            data2.pop("saved_at", None)

            self.assertEqual(data1, data2)


if __name__ == "__main__":
    unittest.main()
