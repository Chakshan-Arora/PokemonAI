"""
Cross-system integration and regression audit tests for Syntax Error 2026.
Verifies lifecycle integrity, cross-manager coordination, failure path atomicity,
encounter accounting, quest event deduplication, player isolation, deterministic
randomness, and save/load schema migrations.
"""
import math
import os
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.species import PokemonSpecies
from src.models.pokemon_type import PokemonType
from src.models.attack import Attack
from src.models.personality import Personality
from src.models.personality_generator import PersonalityGenerator
from src.models.item import Item, ItemType
from src.models.inventory import Inventory
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager, WildEncounter
from src.models.capture_manager import CaptureManager
from src.models.world_interaction import Interactable, InteractableType
from src.models.world_interaction_manager import WorldInteractionManager
from src.models.world_exploration import WorldRegion
from src.models.world_exploration_manager import WorldExplorationManager
from src.models.habitat import (
    TimeOfDay,
    Rarity,
    SpawnCandidate,
    Habitat,
    get_time_of_day,
)
from src.models.habitat_manager import HabitatManager
from src.models.quest import (
    QuestDefinition,
    QuestObjective,
    ObjectiveType,
    QuestEventType,
    QuestStatus,
)
from src.models.quest_manager import QuestManager
from src.models.save_data import SaveDataError, CURRENT_SCHEMA_VERSION
from src.models.save_manager import SaveManager, save_game, load_game
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.items import POTION, SUPER_POTION, ANTIDOTE
from src.data.world_objects import create_default_world_objects
from src.data.world_regions import create_default_world_regions
from src.data.habitats import create_default_habitats
from src.data.quests import TRAILBLAZER, FIRST_ENCOUNTER, SPECIES_RESEARCH, STOCKING_SUPPLIES


class TestSystemIntegration(unittest.TestCase):
    """
    Integration hardening and regression tests across world interaction,
    exploration, habitat encounters, quests, and persistence subsystems.
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()

        # Shared player
        self.player = Player(name="Ash Ketchum", unique_id="player_001", max_team_size=6)

        # Starter Pokemon
        starter = Pokemon(
            species=PIKACHU,
            personality=Personality(50, 50, 50, 50, 50, 50),
            level=5,
            unique_id="10001",
            attacks=PIKACHU.available_attacks,
        )
        self.player.add_pokemon(starter)
        self.player.add_to_team(starter)

        # Managers with fresh default catalogs
        self.exploration_mgr = WorldExplorationManager(regions=create_default_world_regions())
        self.interaction_mgr = WorldInteractionManager(objects=create_default_world_objects())
        self.spawn_mgr = SpawnManager()
        self.encounter_mgr = EncounterManager(spawn_manager=self.spawn_mgr)

        # Register a primary spawn area
        self.test_area = SpawnArea(
            area_id="starting_meadow_spawns",
            name="Starting Meadow Spawns",
            allowed_species=(PIKACHU, CHARMANDER, SQUIRTLE),
            max_active_pokemon=2,
            base_spawn_probability=1.0,
            encounter_radius=10.0,
        )
        self.spawn_mgr.register_area(self.test_area)

        # Habitat manager wired with exploration, spawn, encounter, and quest managers
        self.habitat_mgr = HabitatManager(
            habitats=create_default_habitats(),
            exploration_manager=self.exploration_mgr,
            spawn_manager=self.spawn_mgr,
            encounter_manager=self.encounter_mgr,
            seed=42,
        )

        self.quest_mgr = QuestManager()
        self.exploration_mgr.quest_manager = self.quest_mgr
        self.interaction_mgr.quest_manager = self.quest_mgr
        self.habitat_mgr.quest_manager = self.quest_mgr

    def tearDown(self) -> None:
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    # -------------------------------------------------------------------------
    # 1. World Exploration + Interaction + Quest Progression
    # -------------------------------------------------------------------------

    def test_01_discovery_resource_gathering_and_quest_progression(self) -> None:
        """
        Discovering a region and interacting with objects advances corresponding
        quest objectives without duplicate emissions.
        """
        # Complete prerequisite quest first_encounter
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        self.quest_mgr.record_capture(self.player, "Pikachu", 1, event_id="init_cap_prereq")
        self.assertTrue(self.player.quests["first_encounter"].is_completed)

        # Now accept trailblazer
        acc_res = self.quest_mgr.accept_quest(self.player, "trailblazer")
        self.assertTrue(acc_res.success)
        trailblazer_prog = self.player.quests["trailblazer"]
        self.assertFalse(trailblazer_prog.is_completed)

        # Step into Starting Meadow (coord 5.0, 5.0)
        exp_res = self.exploration_mgr.discover_region_at_position(self.player, (5.0, 5.0))
        self.assertTrue(exp_res.success)
        self.assertTrue(exp_res.is_first_discovery)
        self.assertTrue(exp_res.event_emitted)

        # Trailblazer objective for meadow is satisfied
        meadow_obj = trailblazer_prog.objective_progress["discover_meadow"]
        self.assertTrue(meadow_obj.is_completed)
        self.assertEqual(meadow_obj.current_count, 1)

        # Repeated discovery does not duplicate quest progress
        exp_res_again = self.exploration_mgr.discover_region_at_position(self.player, (5.0, 5.0))
        self.assertTrue(exp_res_again.success)
        self.assertFalse(exp_res_again.is_first_discovery)
        self.assertFalse(exp_res_again.event_emitted)
        self.assertEqual(meadow_obj.current_count, 1)

        # Interacting with Thunder Stone Shrine (at 25.0, 25.0) discovers the landmark
        # and completes the Trailblazer quest
        interact_res = self.interaction_mgr.interact(
            player=self.player,
            object_id="ancient_shrine",
            player_position=(25.0, 25.0),
            current_time=100.0,
            quest_manager=self.quest_mgr,
        )
        self.assertTrue(interact_res.success)
        self.assertTrue(trailblazer_prog.is_completed)
        self.assertEqual(trailblazer_prog.status, QuestStatus.COMPLETED)

    # -------------------------------------------------------------------------
    # 2. Encounter Lifecycle, Concurrency & Active Slot Release
    # -------------------------------------------------------------------------

    def test_02_habitat_encounter_lifecycle_concurrency_and_slot_release(self) -> None:
        """
        EncounterManager prevents concurrent active encounters, releases the
        player slot on resolution, and allows subsequent encounters.
        """
        # Start initial encounter
        enc_res1 = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="starting_meadow_spawns",
        )
        self.assertTrue(enc_res1.success)
        self.assertTrue(self.encounter_mgr.has_active_encounter(self.player))
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 1)

        # Attempt second encounter while first is active -> rejected cleanly
        enc_res2 = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="starting_meadow_spawns",
        )
        self.assertFalse(enc_res2.success)
        self.assertEqual(enc_res2.error_type, "ACTIVE_ENCOUNTER_EXISTS")
        # Population count remains 1 (not incremented on failure)
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 1)

        # Resolve encounter via flee
        resolved_enc = self.habitat_mgr.resolve_encounter(self.player, reason="Fled")
        self.assertIsNotNone(resolved_enc)
        self.assertTrue(resolved_enc.is_resolved)
        self.assertFalse(self.encounter_mgr.has_active_encounter(self.player))
        # Population count decremented back to 0
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 0)

        # Player can now start another encounter cleanly
        enc_res3 = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="starting_meadow_spawns",
        )
        self.assertTrue(enc_res3.success)
        self.assertTrue(self.encounter_mgr.has_active_encounter(self.player))
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 1)

    # -------------------------------------------------------------------------
    # 3. Encounter Resolution Despawns and Prevents Duplicate Decrement
    # -------------------------------------------------------------------------

    def test_03_encounter_resolution_despawns_pokemon_and_prevents_duplicate_despawn(self) -> None:
        """
        Resolving an encounter despawns the wild Pokemon from SpawnManager exactly once,
        and repeated resolution calls return None without altering accounting.
        """
        enc_res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="starting_meadow_spawns",
        )
        self.assertTrue(enc_res.success)
        wild_mon = enc_res.pokemon
        self.assertTrue(self.spawn_mgr.is_pokemon_active("starting_meadow_spawns", wild_mon))
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 1)

        # First resolution
        res1 = self.encounter_mgr.resolve_active_encounter(self.player, reason="Defeated", spawn_manager=self.spawn_mgr)
        self.assertIsNotNone(res1)
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 0)
        self.assertFalse(self.spawn_mgr.is_pokemon_active("starting_meadow_spawns", wild_mon))

        # Second resolution call -> returns None, count remains 0
        res2 = self.encounter_mgr.resolve_active_encounter(self.player, reason="Defeated", spawn_manager=self.spawn_mgr)
        self.assertIsNone(res2)
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 0)

    # -------------------------------------------------------------------------
    # 4. Encounter Resolution Cannot Remove Different Pokemon from Area
    # -------------------------------------------------------------------------

    def test_04_encounter_resolution_cannot_remove_different_pokemon_from_area(self) -> None:
        """
        Resolving one encounter removes only that encounter's Pokemon and
        leaves other wild Pokemon in the same spawn area untouched.
        """
        # Manually spawn another Pokemon in the same area
        other_mon = Pokemon(
            species=CHARMANDER,
            personality=Personality(50, 50, 50, 50, 50, 50),
            level=3,
            unique_id="99999",
            attacks=CHARMANDER.available_attacks,
        )
        self.spawn_mgr.add_active_pokemon("starting_meadow_spawns", other_mon)
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 1)

        # Trigger encounter for player
        enc_res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="starting_meadow_spawns",
        )
        self.assertTrue(enc_res.success)
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 2)

        # Resolve encounter
        self.habitat_mgr.resolve_encounter(self.player, reason="Captured")
        # Total count is 1; other_mon is still active
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 1)
        self.assertTrue(self.spawn_mgr.is_pokemon_active("starting_meadow_spawns", other_mon))

    # -------------------------------------------------------------------------
    # 5. Spawn Area Capacity Exhaustion and Recovery
    # -------------------------------------------------------------------------

    def test_05_spawn_area_capacity_exhaustion_and_recovery(self) -> None:
        """
        When a spawn area reaches max_active_pokemon capacity, further encounter
        spawns fail cleanly without state corruption until space is freed.
        """
        player2 = Player(name="Gary", unique_id="player_002")
        player3 = Player(name="Brock", unique_id="player_003")

        # Fill capacity (max 2)
        res1 = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="starting_meadow_spawns",
        )
        self.assertTrue(res1.success)

        res2 = self.habitat_mgr.trigger_encounter(
            player=player2,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="starting_meadow_spawns",
        )
        self.assertTrue(res2.success)
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 2)
        self.assertFalse(self.spawn_mgr.can_spawn("starting_meadow_spawns"))

        # Third attempt for player 3 fails due to capacity
        res3 = self.habitat_mgr.trigger_encounter(
            player=player3,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="starting_meadow_spawns",
        )
        self.assertFalse(res3.success)
        self.assertEqual(res3.error_type, "SPAWN_CAPACITY_REACHED")
        self.assertFalse(self.encounter_mgr.has_active_encounter(player3))
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 2)

        # Free space by resolving player 1's encounter
        self.habitat_mgr.resolve_encounter(self.player, reason="Fled")
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 1)
        self.assertTrue(self.spawn_mgr.can_spawn("starting_meadow_spawns"))

        # Player 3 can now trigger an encounter
        res3_retry = self.habitat_mgr.trigger_encounter(
            player=player3,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="starting_meadow_spawns",
        )
        self.assertTrue(res3_retry.success)
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 2)

    # -------------------------------------------------------------------------
    # 6. Cooldown Boundary Exact Evaluation
    # -------------------------------------------------------------------------

    def test_06_spawn_area_cooldown_boundaries(self) -> None:
        """
        Spawn area cooldown behaves correctly before, exactly at, and after the deadline.
        """
        area_id = "starting_meadow_spawns"
        self.spawn_mgr.set_area_cooldown(area_id, cooldown_duration=30.0, current_time=100.0)
        deadline = 130.0
        self.assertEqual(self.spawn_mgr.get_area_cooldown(area_id), deadline)

        # Immediately before deadline (129.999) -> on cooldown, cannot spawn
        self.assertTrue(self.spawn_mgr.is_area_on_cooldown(area_id, 129.999))
        self.assertFalse(self.spawn_mgr.can_spawn(area_id, current_time=129.999))
        res_before = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id=area_id,
            current_time=129.999,
        )
        self.assertFalse(res_before.success)
        self.assertEqual(res_before.error_type, "SPAWN_AREA_ON_COOLDOWN")

        # Exactly at deadline (130.000) -> not on cooldown, can spawn
        self.assertFalse(self.spawn_mgr.is_area_on_cooldown(area_id, 130.0))
        self.assertTrue(self.spawn_mgr.can_spawn(area_id, current_time=130.0))

        # Immediately after deadline (130.001) -> can spawn
        self.assertFalse(self.spawn_mgr.is_area_on_cooldown(area_id, 130.001))
        self.assertTrue(self.spawn_mgr.can_spawn(area_id, current_time=130.001))

        res_at = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id=area_id,
            current_time=130.0,
        )
        self.assertTrue(res_at.success)

    # -------------------------------------------------------------------------
    # 7. Treasure Collection Persistence & Duplicate Prevention
    # -------------------------------------------------------------------------

    def test_07_treasure_collection_save_reload_and_duplicate_prevention(self) -> None:
        """
        Looting a treasure persists in save file and prevents re-looting upon reload.
        """
        # Loot treasure supply_cache_01 (at 15.0, 10.0)
        loot_res = self.interaction_mgr.interact(
            player=self.player,
            object_id="supply_cache_01",
            player_position=(15.0, 10.0),
            current_time=50.0,
        )
        self.assertTrue(loot_res.success)
        self.assertTrue(self.player.is_treasure_collected("supply_cache_01"))

        # Save and reload
        save_path = Path(self.temp_dir) / "test_treasure_save.json"
        save_game(self.player, save_path)
        loaded_player = load_game(save_path)

        self.assertTrue(loaded_player.is_treasure_collected("supply_cache_01"))

        # Attempt to loot again with reloaded player
        reloot_res = self.interaction_mgr.interact(
            player=loaded_player,
            object_id="supply_cache_01",
            player_position=(15.0, 10.0),
            current_time=60.0,
        )
        self.assertFalse(reloot_res.success)
        self.assertIn("already been collected", reloot_res.message)

    # -------------------------------------------------------------------------
    # 8. Multi-Item Treasure Atomic Failure on Insufficient Inventory Space
    # -------------------------------------------------------------------------

    def test_08_multi_item_treasure_atomic_failure_on_insufficient_inventory(self) -> None:
        """
        Opening a multi-item treasure with inadequate inventory space fails atomically,
        granting 0 items and leaving the treasure uncollected.
        """
        # Create a restricted player with only 1 slot
        cramped_player = Player(name="Cramped", unique_id="cramped_001", inventory=Inventory(capacity=1))
        cramped_player.inventory.add_item(POTION, 1)  # Slot 1 is occupied

        res = self.interaction_mgr.interact(
            player=cramped_player,
            object_id="supply_cache_01",
            player_position=(15.0, 10.0),
            current_time=50.0,
        )
        self.assertFalse(res.success)
        self.assertIn("Inventory capacity exceeded", res.message)
        self.assertFalse(cramped_player.is_treasure_collected("supply_cache_01"))
        self.assertEqual(cramped_player.inventory.slots_used, 1)
        self.assertEqual(cramped_player.inventory.get_quantity("potion"), 1)
        self.assertEqual(cramped_player.inventory.get_quantity("super_potion"), 0)
        self.assertEqual(cramped_player.inventory.get_quantity("antidote"), 0)

    # -------------------------------------------------------------------------
    # 9. Quest Event Deduplication and No Double Rewards
    # -------------------------------------------------------------------------

    def test_09_quest_event_deduplication_and_no_double_rewards(self) -> None:
        """
        Emitting the same quest event ID twice advances objectives only once,
        and claiming completed quest rewards cannot be performed twice.
        """
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        quest_prog = self.player.quests["first_encounter"]
        self.assertFalse(quest_prog.is_completed)

        event_id = "test_evt_capture_1001"
        res1 = self.quest_mgr.record_capture(
            player=self.player,
            species_name="Pikachu",
            count=1,
            event_id=event_id,
        )
        self.assertEqual(res1.events_processed, 1)
        self.assertEqual(res1.objectives_updated, 1)
        self.assertTrue(quest_prog.is_completed)

        # Replay same event ID
        res2 = self.quest_mgr.record_capture(
            player=self.player,
            species_name="Pikachu",
            count=1,
            event_id=event_id,
        )
        self.assertEqual(res2.events_processed, 0)
        self.assertEqual(res2.objectives_updated, 0)

        # Claim rewards (First Encounter grants 2x potion)
        init_potions = self.player.inventory.get_quantity("potion")
        claim1 = self.quest_mgr.claim_rewards(self.player, "first_encounter")
        self.assertTrue(claim1.success)
        self.assertEqual(self.player.inventory.get_quantity("potion"), init_potions + 2)
        self.assertTrue(quest_prog.rewards_claimed)

        # Duplicate claim attempt is rejected cleanly
        claim2 = self.quest_mgr.claim_rewards(self.player, "first_encounter")
        self.assertFalse(claim2.success)
        self.assertIn("already been claimed", claim2.message)
        self.assertEqual(self.player.inventory.get_quantity("potion"), init_potions + 2)

    # -------------------------------------------------------------------------
    # 10. Multiple Quests Subscribing to Same Event Type
    # -------------------------------------------------------------------------

    def test_10_multiple_quests_subscribing_to_same_event_type(self) -> None:
        """
        When multiple active quests listen to the same event type, both advance
        independently and accurately.
        """
        # Define two distinct quests tracking Pokemon capture
        q1 = QuestDefinition(
            quest_id="catch_one",
            name="Catch One",
            description="Catch one wild Pokemon",
            objectives=(
                QuestObjective(
                    objective_id="catch_any_1",
                    objective_type=ObjectiveType.CAPTURE_ANY,
                    description="Catch any 1 Pokemon",
                    target_count=1,
                ),
            ),
        )
        q2 = QuestDefinition(
            quest_id="catch_two",
            name="Catch Two",
            description="Catch two wild Pokemon",
            objectives=(
                QuestObjective(
                    objective_id="catch_any_2",
                    objective_type=ObjectiveType.CAPTURE_ANY,
                    description="Catch any 2 Pokemon",
                    target_count=2,
                ),
            ),
        )
        custom_qm = QuestManager(catalog={"catch_one": q1, "catch_two": q2})
        custom_qm.accept_quest(self.player, "catch_one")
        custom_qm.accept_quest(self.player, "catch_two")

        # Emit capture event 1
        res1 = custom_qm.record_capture(self.player, species_name="Pikachu", count=1, event_id="evt_01")
        self.assertEqual(res1.objectives_updated, 2)
        self.assertTrue(self.player.quests["catch_one"].is_completed)
        self.assertFalse(self.player.quests["catch_two"].is_completed)
        self.assertEqual(self.player.quests["catch_two"].objective_progress["catch_any_2"].current_count, 1)

        # Emit capture event 2
        res2 = custom_qm.record_capture(self.player, species_name="Charmander", count=1, event_id="evt_02")
        self.assertEqual(res2.objectives_updated, 1)  # only q2 was updated (q1 was already completed)
        self.assertTrue(self.player.quests["catch_two"].is_completed)

    # -------------------------------------------------------------------------
    # 11. Unrelated Objectives Not Progressed by Encounter Event
    # -------------------------------------------------------------------------

    def test_11_unrelated_quest_objectives_not_progressed_by_encounter_event(self) -> None:
        """
        Emitting a POKEMON_ENCOUNTERED event does not accidentally increment
        CAPTURE_ANY, CAPTURE_SPECIES, or DEFEAT_ANY objectives.
        """
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        self.quest_mgr.accept_quest(self.player, "wild_challenger")

        # Trigger wild encounter
        enc_res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
        )
        self.assertTrue(enc_res.success)
        self.assertTrue(enc_res.event_emitted)

        # Neither capture quest nor defeat quest should have progressed
        first_enc_prog = self.player.quests["first_encounter"]
        wild_chal_prog = self.player.quests["wild_challenger"]
        self.assertFalse(first_enc_prog.is_completed)
        self.assertEqual(first_enc_prog.objective_progress["capture_first_pokemon"].current_count, 0)
        self.assertFalse(wild_chal_prog.is_completed)
        self.assertEqual(wild_chal_prog.objective_progress["defeat_any_pokemon"].current_count, 0)

    # -------------------------------------------------------------------------
    # 12. Two-Player Complete Isolation
    # -------------------------------------------------------------------------

    def test_12_two_player_complete_isolation(self) -> None:
        """
        Two player instances operating in the same world maintain strictly isolated
        discoveries, treasures, encounter sessions, and quest progress.
        """
        player_b = Player(name="Blue", unique_id="player_002")

        # Player A discovers meadow; Player B does not
        self.exploration_mgr.discover_region(self.player, "starting_meadow")
        self.assertTrue(self.player.is_region_discovered("starting_meadow"))
        self.assertFalse(player_b.is_region_discovered("starting_meadow"))

        # Player A loots treasure supply_cache_01
        res_a = self.interaction_mgr.interact(self.player, "supply_cache_01", (15.0, 10.0), current_time=10.0)
        self.assertTrue(res_a.success)
        self.assertTrue(self.player.is_treasure_collected("supply_cache_01"))
        self.assertFalse(player_b.is_treasure_collected("supply_cache_01"))

        # Player B can independently loot supply_cache_01
        res_b = self.interaction_mgr.interact(player_b, "supply_cache_01", (15.0, 10.0), current_time=20.0)
        self.assertTrue(res_b.success)
        self.assertTrue(player_b.is_treasure_collected("supply_cache_01"))

        # Player A has an active encounter; Player B does not
        enc_a = self.habitat_mgr.trigger_encounter(self.player, region_id="starting_meadow", time_of_day=TimeOfDay.DAY)
        self.assertTrue(enc_a.success)
        self.assertTrue(self.encounter_mgr.has_active_encounter(self.player))
        self.assertFalse(self.encounter_mgr.has_active_encounter(player_b))

        # Player B can start their own independent encounter
        enc_b = self.habitat_mgr.trigger_encounter(player_b, region_id="forest_trail", time_of_day=TimeOfDay.DAY)
        self.assertTrue(enc_b.success)
        self.assertTrue(self.encounter_mgr.has_active_encounter(player_b))

    # -------------------------------------------------------------------------
    # 13. Deterministic Time Periods & Midnight Boundary
    # -------------------------------------------------------------------------

    def test_13_deterministic_time_periods_and_midnight_boundary(self) -> None:
        """
        Verifies exact hour boundaries including midnight 0.0, floating boundaries,
        and transitions across all 4 TimeOfDay enum periods.
        """
        # Midnight and night hours
        self.assertEqual(get_time_of_day(0.0), TimeOfDay.NIGHT)
        self.assertEqual(get_time_of_day(2.5), TimeOfDay.NIGHT)
        self.assertEqual(get_time_of_day(4.999), TimeOfDay.NIGHT)

        # Morning: 05:00 <= hour < 10:00
        self.assertEqual(get_time_of_day(5.0), TimeOfDay.MORNING)
        self.assertEqual(get_time_of_day(7.5), TimeOfDay.MORNING)
        self.assertEqual(get_time_of_day(9.999), TimeOfDay.MORNING)

        # Day: 10:00 <= hour < 17:00
        self.assertEqual(get_time_of_day(10.0), TimeOfDay.DAY)
        self.assertEqual(get_time_of_day(13.25), TimeOfDay.DAY)
        self.assertEqual(get_time_of_day(16.999), TimeOfDay.DAY)

        # Evening: 17:00 <= hour < 21:00
        self.assertEqual(get_time_of_day(17.0), TimeOfDay.EVENING)
        self.assertEqual(get_time_of_day(19.0), TimeOfDay.EVENING)
        self.assertEqual(get_time_of_day(20.999), TimeOfDay.EVENING)

        # Night: 21:00 <= hour < 24.0
        self.assertEqual(get_time_of_day(21.0), TimeOfDay.NIGHT)
        self.assertEqual(get_time_of_day(23.5), TimeOfDay.NIGHT)
        self.assertEqual(get_time_of_day(23.9999), TimeOfDay.NIGHT)

    # -------------------------------------------------------------------------
    # 14. Invalid Time Inputs Fail Cleanly
    # -------------------------------------------------------------------------

    def test_14_invalid_time_inputs_fail_cleanly(self) -> None:
        """
        get_time_of_day rejects negative hours, 24.0, NaN, infinity, and non-numeric types.
        """
        with self.assertRaises(ValueError):
            get_time_of_day(-0.001)

        with self.assertRaises(ValueError):
            get_time_of_day(-12.0)

        with self.assertRaises(ValueError):
            get_time_of_day(24.0)

        with self.assertRaises(ValueError):
            get_time_of_day(25.5)

        with self.assertRaises(ValueError):
            get_time_of_day(float("nan"))

        with self.assertRaises(ValueError):
            get_time_of_day(float("inf"))

        with self.assertRaises(ValueError):
            get_time_of_day(float("-inf"))

        with self.assertRaises(TypeError):
            get_time_of_day("12:00")  # type: ignore

        with self.assertRaises(TypeError):
            get_time_of_day(True)  # type: ignore

        with self.assertRaises(TypeError):
            get_time_of_day(None)  # type: ignore

    # -------------------------------------------------------------------------
    # 15. Deterministic Seeded RNG Reproducibility
    # -------------------------------------------------------------------------

    def test_15_deterministic_seeded_rng_encounter_reproducibility(self) -> None:
        """
        Two independent HabitatManager instances initialized with the same seed
        produce identical sequences of species, levels, and personality traits.
        """
        hm1 = HabitatManager(seed=98765)
        hm2 = HabitatManager(seed=98765)

        p1 = Player("P1")
        p2 = Player("P2")

        for _ in range(5):
            res1 = hm1.trigger_encounter(p1, region_id="forest_trail", time_of_day=TimeOfDay.DAY)
            res2 = hm2.trigger_encounter(p2, region_id="forest_trail", time_of_day=TimeOfDay.DAY)

            self.assertTrue(res1.success)
            self.assertTrue(res2.success)
            self.assertEqual(res1.pokemon.species.name, res2.pokemon.species.name)
            self.assertEqual(res1.pokemon.level, res2.pokemon.level)
            self.assertEqual(res1.pokemon.personality.to_dict(), res2.pokemon.personality.to_dict())

            hm1.resolve_encounter(p1)
            hm2.resolve_encounter(p2)

    # -------------------------------------------------------------------------
    # 16. Save Schema v1, v2, v3 to v4 Migration
    # -------------------------------------------------------------------------

    def test_16_schema_v1_v2_v3_to_v4_migration_cross_system_integrity(self) -> None:
        """
        Verifies that legacy saves from Schema v1, v2, and v3 migrate cleanly
        into Schema v4 with expected default collections.
        """
        base_payload = {
            "player": {
                "name": "Red",
                "unique_id": "player_red",
                "max_team_size": 6,
            },
            "inventory": {
                "capacity": 20,
                "items": {"potion": 5},
            },
            "collection": [
                {
                    "unique_id": "10001",
                    "species": "Pikachu",
                    "nickname": None,
                    "level": 5,
                    "experience": 0,
                    "current_hp": 21,
                    "personality": {
                        "aggression": 50,
                        "curiosity": 50,
                        "fear": 50,
                        "sociability": 50,
                        "loyalty": 50,
                        "confidence": 50,
                    },
                    "bond": 10,
                    "obedience": 100,
                    "attacks": ["Thunder Shock"],
                    "trained_stats": {"attack": 0, "defense": 0, "speed": 0},
                    "awarded_level_moves": [],
                }
            ],
            "team": ["10001"],
            "active_pokemon_id": "10001",
        }

        # Schema v1 payload (no quests, no treasures, no exploration)
        v1_data = dict(base_payload)
        v1_data["schema_version"] = 1
        p_v1 = SaveManager.deserialize(v1_data)
        self.assertEqual(p_v1.quests, {})
        self.assertEqual(p_v1.collected_treasures, set())
        self.assertEqual(p_v1.discovered_regions, set())
        self.assertEqual(p_v1.discovered_landmarks, set())

        # Schema v2 payload (has quests, no treasures, no exploration)
        v2_data = dict(base_payload)
        v2_data["schema_version"] = 2
        v2_data["quests"] = {
            "first_encounter": {
                "status": "completed",
                "is_completed": True,
                "rewards_claimed": True,
                "objective_progress": {
                    "capture_first_pokemon": {"current_count": 1}
                },
            }
        }
        p_v2 = SaveManager.deserialize(v2_data)
        self.assertIn("first_encounter", p_v2.quests)
        self.assertEqual(p_v2.collected_treasures, set())
        self.assertEqual(p_v2.discovered_regions, set())

        # Schema v3 payload (has quests and treasures, no exploration)
        v3_data = dict(v2_data)
        v3_data["schema_version"] = 3
        v3_data["collected_treasures"] = ["supply_cache_01"]
        p_v3 = SaveManager.deserialize(v3_data)
        self.assertIn("first_encounter", p_v3.quests)
        self.assertIn("supply_cache_01", p_v3.collected_treasures)
        self.assertEqual(p_v3.discovered_regions, set())
        self.assertEqual(p_v3.discovered_landmarks, set())

    # -------------------------------------------------------------------------
    # 17. Failed Encounters Leave All Managers and Player Unmutated
    # -------------------------------------------------------------------------

    def test_17_failed_encounters_leave_all_managers_and_player_unmutated(self) -> None:
        """
        Failed encounter attempts (e.g. unknown region, diurnal species queried at night)
        leave spawn counts, player active encounter slots, and quest progress completely unmutated.
        """
        init_count = self.spawn_mgr.get_active_count("starting_meadow_spawns")
        self.assertFalse(self.encounter_mgr.has_active_encounter(self.player))

        # Query Starting Meadow at NIGHT (Meadow candidates are Pikachu [M/D] and Squirtle [D/E])
        res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.NIGHT,
            area_id="starting_meadow_spawns",
        )
        self.assertFalse(res.success)
        self.assertEqual(res.error_type, "NO_ELIGIBLE_SPECIES")
        self.assertFalse(res.event_emitted)
        self.assertFalse(self.encounter_mgr.has_active_encounter(self.player))
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), init_count)

    # -------------------------------------------------------------------------
    # 18. Capture Resolution Despawns Pokemon from SpawnManager
    # -------------------------------------------------------------------------

    def test_18_capture_resolution_despawns_pokemon_using_encounter_area(self) -> None:
        """
        Capturing a wild Pokemon resolves the WildEncounter and despawns the wild Pokemon
        from SpawnManager even when area_id is not explicitly passed to attempt_capture.
        """
        enc_res = self.habitat_mgr.trigger_encounter(
            player=self.player,
            region_id="starting_meadow",
            time_of_day=TimeOfDay.DAY,
            area_id="starting_meadow_spawns",
        )
        self.assertTrue(enc_res.success)
        wild_mon = enc_res.pokemon
        wild_enc = enc_res.encounter
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 1)

        cap_mgr = CaptureManager(seed=1)  # Seed guaranteed to catch
        # We pass encounter and spawn_manager, but omit area_id
        cap_res = cap_mgr.attempt_capture(
            player=self.player,
            wild_pokemon=wild_mon,
            encounter=wild_enc,
            spawn_manager=self.spawn_mgr,
        )
        self.assertTrue(cap_res.success)
        self.assertTrue(wild_enc.is_resolved)
        self.assertFalse(self.encounter_mgr.has_active_encounter(self.player))
        # Wild pokemon was automatically despawned from the area
        self.assertEqual(self.spawn_mgr.get_active_count("starting_meadow_spawns"), 0)

    # -------------------------------------------------------------------------
    # 19. Replaying Event on Completed Quest Leaves Rewards and State Intact
    # -------------------------------------------------------------------------

    def test_19_replaying_event_on_completed_quest_leaves_rewards_and_state_intact(self) -> None:
        """
        Replaying an event after a quest is completed and rewards claimed does not
        alter quest status, progress count, or rewards.
        """
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        evt_id = "initial_capture_001"
        self.quest_mgr.record_capture(self.player, "Pikachu", 1, event_id=evt_id)
        self.quest_mgr.claim_rewards(self.player, "first_encounter")

        qp = self.player.quests["first_encounter"]
        self.assertEqual(qp.status, QuestStatus.COMPLETED)
        self.assertTrue(qp.rewards_claimed)

        # Replay event
        replay_res = self.quest_mgr.record_capture(self.player, "Pikachu", 1, event_id=evt_id)
        self.assertEqual(replay_res.events_processed, 0)
        self.assertEqual(qp.status, QuestStatus.COMPLETED)
        self.assertTrue(qp.rewards_claimed)

    # -------------------------------------------------------------------------
    # 20. Encounter Objectives Advance on Encounter Events
    # -------------------------------------------------------------------------

    def test_20_encounter_objectives_advance_with_encounter_events(self) -> None:
        """
        Quests with ENCOUNTER_ANY and ENCOUNTER_SPECIES objectives advance
        properly when POKEMON_ENCOUNTERED events are emitted.
        """
        encounter_quest = QuestDefinition(
            quest_id="field_research",
            name="Field Research",
            description="Encounter wild Pokemon in nature",
            objectives=(
                QuestObjective(
                    objective_id="encounter_any_1",
                    objective_type=ObjectiveType.ENCOUNTER_ANY,
                    description="Encounter any wild Pokemon",
                    target_count=2,
                ),
                QuestObjective(
                    objective_id="encounter_pika_1",
                    objective_type=ObjectiveType.ENCOUNTER_SPECIES,
                    description="Encounter a wild Pikachu",
                    target_count=1,
                    target_species="Pikachu",
                ),
            ),
        )
        custom_qm = QuestManager(catalog={"field_research": encounter_quest})
        custom_qm.accept_quest(self.player, "field_research")
        qp = self.player.quests["field_research"]

        # Encounter Pikachu
        res1 = custom_qm.record_encounter(self.player, species_name="Pikachu", habitat_id="meadow", event_id="enc_01")
        self.assertEqual(res1.objectives_updated, 2)
        self.assertEqual(qp.objective_progress["encounter_any_1"].current_count, 1)
        self.assertEqual(qp.objective_progress["encounter_pika_1"].current_count, 1)
        self.assertTrue(qp.objective_progress["encounter_pika_1"].is_completed)
        self.assertFalse(qp.is_completed)

        # Encounter Charmander
        res2 = custom_qm.record_encounter(self.player, species_name="Charmander", habitat_id="meadow", event_id="enc_02")
        self.assertEqual(res2.objectives_updated, 1)
        self.assertEqual(qp.objective_progress["encounter_any_1"].current_count, 2)
        self.assertTrue(qp.objective_progress["encounter_any_1"].is_completed)
        self.assertTrue(qp.is_completed)


if __name__ == "__main__":
    unittest.main()
