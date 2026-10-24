"""
Unit tests for the World Interaction & Resource Gathering Subsystem.
Verifies object registration, proximity validation, resource gathering,
deterministic respawning, treasure collection and persistence, atomic rewards,
inventory bounds, quest integration, and schema migration.
"""
import unittest
import tempfile
from pathlib import Path

from src.models.player import Player
from src.models.inventory import Inventory
from src.models.save_data import CURRENT_SCHEMA_VERSION, SaveDataError
from src.models.save_manager import (
    serialize_player,
    deserialize_player,
    save_game,
    load_game,
)
from src.models.world_interaction import (
    InteractableType,
    Interactable,
    InteractionResult,
)
from src.models.world_interaction_manager import WorldInteractionManager
from src.models.quest_manager import QuestManager
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.status_effect import StatusEffect, StatusEffectType
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.world_regions import WORLD_REGION_CATALOG
from src.data.world_objects import (
    BERRY_BUSH,
    SUPPLY_CACHE,
    ROUTE1_SIGN,
    ANCIENT_SHRINE,
    POKEMON_CENTER_MEADOW,
    WORLD_OBJECT_CATALOG,
    get_world_object,
    create_default_world_objects,
)


class TestWorldInteractionManager(unittest.TestCase):
    """
    Exhaustive test suite for world object interactions, respawns, rewards, and persistence.
    """

    def setUp(self) -> None:
        self.player = Player(name="Red", inventory=Inventory(capacity=20))
        # Controllable deterministic clock
        self.current_time = 100.0
        self.manager = WorldInteractionManager(
            clock=lambda: self.current_time,
        )

    # --- 1. Model Validation & Registration Tests ---

    def test_01_interactable_validation(self) -> None:
        """Interactable validates IDs, positions, radii, rewards, and signs."""
        # Valid creation
        obj = Interactable(
            object_id="test_node",
            name="Test Node",
            description="A test object",
            interactable_type=InteractableType.RESOURCE_NODE,
            position=(10.0, 20.0),
            interaction_radius=2.5,
            rewards={"potion": 1},
            respawn_duration=30.0,
        )
        self.assertEqual(obj.object_id, "test_node")
        self.assertEqual(obj.position, (10.0, 20.0))
        self.assertEqual(obj.interaction_radius, 2.5)

        # Empty ID rejected
        with self.assertRaises(ValueError):
            Interactable(
                object_id="",
                name="Test",
                description="Desc",
                interactable_type=InteractableType.RESOURCE_NODE,
                position=(0.0, 0.0),
            )

        # Invalid position format rejected
        with self.assertRaises(ValueError):
            Interactable(
                object_id="bad_pos",
                name="Test",
                description="Desc",
                interactable_type=InteractableType.RESOURCE_NODE,
                position=(0.0,),  # type: ignore
            )

        # Invalid radius rejected
        with self.assertRaises(ValueError):
            Interactable(
                object_id="bad_rad",
                name="Test",
                description="Desc",
                interactable_type=InteractableType.RESOURCE_NODE,
                position=(0.0, 0.0),
                interaction_radius=0.0,
            )

        # Sign missing interaction_text rejected
        with self.assertRaises(ValueError):
            Interactable(
                object_id="bad_sign",
                name="Sign",
                description="Desc",
                interactable_type=InteractableType.SIGN,
                position=(0.0, 0.0),
                interaction_text=None,
            )

    def test_02_register_and_retrieve_objects(self) -> None:
        """Objects can be registered, retrieved by ID, and unregistered cleanly."""
        custom = Interactable(
            object_id="custom_box",
            name="Wooden Box",
            description="A simple box",
            interactable_type=InteractableType.TREASURE,
            position=(1.0, 1.0),
            rewards={"potion": 1},
        )
        self.manager.register_object(custom)
        retrieved = self.manager.get_object("custom_box")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Wooden Box")

        # Case-insensitive lookup
        self.assertIsNotNone(self.manager.get_object("CUSTOM_BOX"))

        # Unregister
        self.assertTrue(self.manager.unregister_object("custom_box"))
        self.assertIsNone(self.manager.get_object("custom_box"))

    def test_03_unknown_object_id_handling(self) -> None:
        """Interacting with or querying an unknown object fails cleanly."""
        can_do, reason = self.manager.can_interact(
            self.player, "nonexistent_obj", (0.0, 0.0), self.current_time
        )
        self.assertFalse(can_do)
        self.assertIn("not found", reason.lower())

        res = self.manager.interact(
            self.player, "nonexistent_obj", (0.0, 0.0), self.current_time
        )
        self.assertFalse(res.success)
        self.assertIn("not found", res.message.lower())

    # --- 2. Proximity & Coordinate Validation Tests ---

    def test_04_inside_and_outside_radius_interactions(self) -> None:
        """Interaction succeeds within interaction radius and fails outside radius."""
        # Berry bush is at (5.0, 5.0) with radius 2.0
        # Position at (5.0, 6.0) -> distance 1.0 <= 2.0 (Inside)
        can_do, _ = self.manager.can_interact(
            self.player, "berry_bush_route1", (5.0, 6.0), self.current_time
        )
        self.assertTrue(can_do)

        # Position at (5.0, 8.0) -> distance 3.0 > 2.0 (Outside)
        can_do_far, reason_far = self.manager.can_interact(
            self.player, "berry_bush_route1", (5.0, 8.0), self.current_time
        )
        self.assertFalse(can_do_far)
        self.assertIn("out of range", reason_far.lower())

        # Direct interact outside radius returns failure
        res_far = self.manager.interact(
            self.player, "berry_bush_route1", (5.0, 8.0), self.current_time
        )
        self.assertFalse(res_far.success)
        self.assertIn("out of range", res_far.message.lower())
        self.assertEqual(self.player.inventory.get_quantity("potion"), 0)

    def test_05_invalid_player_position_handling(self) -> None:
        """Malformed player position coordinates return clean failure without crashes."""
        res_bad_dim = self.manager.interact(
            self.player, "berry_bush_route1", (5.0,), self.current_time  # type: ignore
        )
        self.assertFalse(res_bad_dim.success)
        self.assertIn("invalid player position", res_bad_dim.message.lower())

        res_bad_val = self.manager.interact(
            self.player, "berry_bush_route1", ("five", 5.0), self.current_time  # type: ignore
        )
        self.assertFalse(res_bad_val.success)
        self.assertIn("invalid player position", res_bad_val.message.lower())

    def test_06_list_objects_in_range(self) -> None:
        """list_objects_in_range returns only objects within spatial distance."""
        # Route 1 sign is at (2.0, 1.0)
        # Berry bush is at (5.0, 5.0)
        # Ancient shrine is at (25.0, 25.0)
        nearby = self.manager.list_objects_in_range((2.0, 1.0), radius=5.0)
        nearby_ids = [o.object_id for o in nearby]
        self.assertIn("route1_sign", nearby_ids)
        self.assertNotIn("ancient_shrine", nearby_ids)

    # --- 3. Resource Gathering & Respawn Cycle Tests ---

    def test_07_successful_resource_gathering(self) -> None:
        """Gathering from a resource node grants items and initiates respawn cooldown."""
        bush = self.manager.get_object("berry_bush_route1")
        self.assertTrue(bush.is_available)

        res = self.manager.interact(
            self.player, "berry_bush_route1", (5.0, 5.0), self.current_time
        )
        self.assertTrue(res.success)
        self.assertEqual(res.items_granted, {"potion": 1})
        self.assertEqual(self.player.inventory.get_quantity("potion"), 1)
        self.assertFalse(bush.is_available)
        self.assertEqual(bush.respawn_deadline, self.current_time + 60.0)

    def test_08_resource_unavailable_before_respawn_deadline(self) -> None:
        """Gathered resource node cannot be harvested again before its respawn deadline."""
        self.manager.interact(
            self.player, "berry_bush_route1", (5.0, 5.0), self.current_time
        )

        # Advance time by 30 seconds (deadline is +60s)
        time_mid = self.current_time + 30.0
        self.assertFalse(
            self.manager.is_object_available("berry_bush_route1", self.player, time_mid)
        )

        can_do, reason = self.manager.can_interact(
            self.player, "berry_bush_route1", (5.0, 5.0), time_mid
        )
        self.assertFalse(can_do)
        self.assertIn("depleted", reason.lower())

        res2 = self.manager.interact(
            self.player, "berry_bush_route1", (5.0, 5.0), time_mid
        )
        self.assertFalse(res2.success)
        self.assertIn("depleted", res2.message.lower())
        # Inventory remains unchanged at 1
        self.assertEqual(self.player.inventory.get_quantity("potion"), 1)

    def test_09_resource_available_at_or_after_respawn_deadline(self) -> None:
        """Resource node becomes available at or after respawn deadline and can be regathered."""
        self.manager.interact(
            self.player, "berry_bush_route1", (5.0, 5.0), self.current_time
        )

        # Advance time exactly to deadline (+60s)
        time_respawn = self.current_time + 60.0
        self.assertTrue(
            self.manager.is_object_available("berry_bush_route1", self.player, time_respawn)
        )

        # Harvest again
        res = self.manager.interact(
            self.player, "berry_bush_route1", (5.0, 5.0), time_respawn
        )
        self.assertTrue(res.success)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 2)

    def test_10_check_respawns_method(self) -> None:
        """check_respawns updates object flags and returns respawned object IDs."""
        self.manager.interact(
            self.player, "berry_bush_route1", (5.0, 5.0), self.current_time
        )
        bush = self.manager.get_object("berry_bush_route1")
        self.assertFalse(bush.is_available)

        # Check before deadline
        respawned = self.manager.check_respawns(self.current_time + 20.0)
        self.assertEqual(respawned, [])
        self.assertFalse(bush.is_available)

        # Check at deadline
        respawned = self.manager.check_respawns(self.current_time + 60.0)
        self.assertIn("berry_bush_route1", respawned)
        self.assertTrue(bush.is_available)
        self.assertIsNone(bush.respawn_deadline)

    # --- 4. Treasure Collection & One-Time Rules ---

    def test_11_treasure_collection_and_duplicate_prevention(self) -> None:
        """Opening a treasure grants items, marks it collected, and prevents duplicate looting."""
        cache = self.manager.get_object("supply_cache_01")
        self.assertFalse(self.player.is_treasure_collected("supply_cache_01"))

        # Open cache at (15.0, 10.0)
        res = self.manager.interact(
            self.player, "supply_cache_01", (15.0, 10.0), self.current_time
        )
        self.assertTrue(res.success)
        self.assertEqual(res.items_granted, {"super_potion": 1, "antidote": 2})
        self.assertEqual(self.player.inventory.get_quantity("super_potion"), 1)
        self.assertEqual(self.player.inventory.get_quantity("antidote"), 2)
        self.assertTrue(self.player.is_treasure_collected("supply_cache_01"))

        # Second attempt rejected
        res2 = self.manager.interact(
            self.player, "supply_cache_01", (15.0, 10.0), self.current_time + 100.0
        )
        self.assertFalse(res2.success)
        self.assertIn("already been collected", res2.message.lower())
        # Quantities unchanged
        self.assertEqual(self.player.inventory.get_quantity("super_potion"), 1)
        self.assertEqual(self.player.inventory.get_quantity("antidote"), 2)

    # --- 5. Sign and Landmark Interaction Tests ---

    def test_12_sign_interaction_returns_text_without_items(self) -> None:
        """Reading a sign returns its text without granting items or changing inventory."""
        res = self.manager.interact(
            self.player, "route1_sign", (2.0, 1.0), self.current_time
        )
        self.assertTrue(res.success)
        self.assertEqual(res.items_granted, {})
        self.assertIn("Viridian City", res.interaction_text)
        self.assertEqual(len(self.player.inventory), 0)

    def test_13_landmark_discovery_interaction(self) -> None:
        """Interacting with a landmark reports discovery without consuming items."""
        res = self.manager.interact(
            self.player, "ancient_shrine", (25.0, 25.0), self.current_time
        )
        self.assertTrue(res.success)
        self.assertTrue(res.is_discovered)
        self.assertEqual(res.items_granted, {})
        self.assertIn("Thunder Stone Shrine", res.message)

    # --- 6. Atomic Rewards & Inventory Limits ---

    def test_14_atomic_reward_delivery_multi_item(self) -> None:
        """Treasure with multiple items delivers all items atomically."""
        res = self.manager.interact(
            self.player, "supply_cache_01", (15.0, 10.0), self.current_time
        )
        self.assertTrue(res.success)
        self.assertEqual(self.player.inventory.get_quantity("super_potion"), 1)
        self.assertEqual(self.player.inventory.get_quantity("antidote"), 2)

    def test_15_full_inventory_capacity_failure_is_atomic(self) -> None:
        """When inventory is full, interaction fails without granting partial items or depleting node."""
        small_inv = Inventory(capacity=1)
        small_inv.add_item("potion", 1)  # 1/1 slots occupied
        constrained_player = Player(name="FullBag", inventory=small_inv)

        # Supply cache grants super_potion and antidote, requiring new slots
        res = self.manager.interact(
            constrained_player, "supply_cache_01", (15.0, 10.0), self.current_time
        )
        self.assertFalse(res.success)
        self.assertIn("capacity exceeded", res.message.lower())

        # Inventory completely untouched
        self.assertEqual(constrained_player.inventory.slots_used, 1)
        self.assertEqual(constrained_player.inventory.get_quantity("super_potion"), 0)
        self.assertEqual(constrained_player.inventory.get_quantity("antidote"), 0)

        # Treasure remains uncollected
        self.assertFalse(constrained_player.is_treasure_collected("supply_cache_01"))
        cache = self.manager.get_object("supply_cache_01")
        self.assertTrue(cache.is_available)

    def test_16_failed_interaction_does_not_start_respawn_timer(self) -> None:
        """Failed interaction (due to full inventory) does not set respawn cooldown on resource node."""
        small_inv = Inventory(capacity=1)
        small_inv.add_item("antidote", 1)  # Occupied with antidote
        constrained_player = Player(name="FullBag", inventory=small_inv)

        # Berry bush grants potion, requiring a new slot
        bush = self.manager.get_object("berry_bush_route1")
        res = self.manager.interact(
            constrained_player, "berry_bush_route1", (5.0, 5.0), self.current_time
        )
        self.assertFalse(res.success)

        # Bush must remain available and have NO respawn deadline
        self.assertTrue(bush.is_available)
        self.assertIsNone(bush.respawn_deadline)

    # --- 7. Quest Integration & Event Deduplication ---

    def test_17_quest_integration_emits_event_on_successful_reward(self) -> None:
        """Successful resource gathering advances item collection quests."""
        qm = QuestManager()
        qm.accept_quest(self.player, "stocking_supplies")  # Collect 3 potions
        self.manager.quest_manager = qm

        q_prog = qm.get_quest_progress(self.player, "stocking_supplies")
        self.assertEqual(q_prog.objective_progress["collect_potions"].current_count, 0)

        # Gather from berry bush (grants 1 potion)
        res = self.manager.interact(
            self.player, "berry_bush_route1", (5.0, 5.0), self.current_time
        )
        self.assertTrue(res.success)

        # Quest progress must have advanced to 1
        self.assertEqual(q_prog.objective_progress["collect_potions"].current_count, 1)

    def test_18_failed_interaction_emits_no_quest_progress(self) -> None:
        """Failed interaction (out of range) does not emit quest progress."""
        qm = QuestManager()
        qm.accept_quest(self.player, "stocking_supplies")
        self.manager.quest_manager = qm

        # Attempt interaction out of range
        res = self.manager.interact(
            self.player, "berry_bush_route1", (50.0, 50.0), self.current_time
        )
        self.assertFalse(res.success)

        # Quest progress remains 0
        q_prog = qm.get_quest_progress(self.player, "stocking_supplies")
        self.assertEqual(q_prog.objective_progress["collect_potions"].current_count, 0)

    # --- 8. Player Isolation & Save/Load Persistence ---

    def test_19_player_treasure_isolation(self) -> None:
        """One player collecting a treasure does not prevent another player from collecting it."""
        player_b = Player(name="Blue", inventory=Inventory(capacity=20))

        # Red opens the cache
        self.manager.interact(
            self.player, "supply_cache_01", (15.0, 10.0), self.current_time
        )
        self.assertTrue(self.player.is_treasure_collected("supply_cache_01"))

        # Blue has not collected it
        self.assertFalse(player_b.is_treasure_collected("supply_cache_01"))
        self.assertTrue(
            self.manager.is_object_available("supply_cache_01", player_b, self.current_time)
        )

        # Blue can open the cache independently
        res_blue = self.manager.interact(
            player_b, "supply_cache_01", (15.0, 10.0), self.current_time
        )
        self.assertTrue(res_blue.success)
        self.assertTrue(player_b.is_treasure_collected("supply_cache_01"))
        self.assertEqual(player_b.inventory.get_quantity("super_potion"), 1)

    def test_20_save_load_round_trip_persists_collected_treasures(self) -> None:
        """Collected treasure IDs persist across serialization and save/load round-trip."""
        self.player.mark_treasure_collected("supply_cache_01")

        save_data = serialize_player(self.player)
        self.assertEqual(save_data["schema_version"], CURRENT_SCHEMA_VERSION)
        self.assertIn("collected_treasures", save_data)
        self.assertIn("supply_cache_01", save_data["collected_treasures"])

        # Deserialize into new instance
        restored = deserialize_player(save_data)
        self.assertEqual(restored.name, "Red")
        self.assertTrue(restored.is_treasure_collected("supply_cache_01"))

        # Restored player cannot open treasure again
        self.assertFalse(
            self.manager.is_object_available("supply_cache_01", restored, self.current_time)
        )
        res = self.manager.interact(
            restored, "supply_cache_01", (15.0, 10.0), self.current_time
        )
        self.assertFalse(res.success)
        self.assertIn("already been collected", res.message.lower())

    def test_21_schema_v1_and_v2_migration(self) -> None:
        """Schema versions 1 and 2 migrate cleanly with empty collected treasures."""
        # Schema 1 payload
        v1_data = {
            "schema_version": 1,
            "player": {"name": "OldPlayer", "unique_id": "old-001", "max_team_size": 6},
            "inventory": {"capacity": 20, "items": {}},
            "collection": [],
            "team": [],
            "active_pokemon_id": None,
        }
        p1 = deserialize_player(v1_data)
        self.assertEqual(p1.collected_treasures, set())

        # Schema 2 payload
        v2_data = {
            "schema_version": 2,
            "player": {"name": "MidPlayer", "unique_id": "mid-002", "max_team_size": 6},
            "inventory": {"capacity": 20, "items": {}},
            "collection": [],
            "team": [],
            "active_pokemon_id": None,
            "quests": {},
        }
        p2 = deserialize_player(v2_data)
        self.assertEqual(p2.collected_treasures, set())

    def test_22_corrupt_treasure_data_rejected(self) -> None:
        """Unknown treasure IDs or non-treasure objects in save payload raise SaveDataError."""
        save_data = serialize_player(self.player)

        # Unknown treasure ID
        bad_data = dict(save_data)
        bad_data["collected_treasures"] = ["unknown_chest_999"]
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(bad_data)
        self.assertIn("unknown collected treasure", str(ctx.exception).lower())

        # Object that is a sign, not a treasure
        bad_type_data = dict(save_data)
        bad_type_data["collected_treasures"] = ["route1_sign"]
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(bad_type_data)
        self.assertIn("not treasure", str(ctx.exception).lower())

    # --- 8. Pokemon Center Healing & Stat Restoration Tests ---

    def test_23_pokemon_center_heals_all_pokemon_and_restores_stats(self) -> None:
        """Pokemon Center heals damaged Pokemon and resets combat stat debuffs to default values."""
        personality = Personality(aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50)
        p1 = Pokemon(species=PIKACHU, personality=personality, level=5)
        p2 = Pokemon(species=CHARMANDER, personality=personality, level=5)
        self.player.add_pokemon(p1)
        self.player.add_to_team(p1)
        self.player.add_pokemon(p2)
        self.player.add_to_team(p2)

        # Damage and inflict status debuffs
        p1.take_damage(20)
        p2.take_damage(15)
        p1.add_status_effect(StatusEffect(StatusEffectType.ATTACK_REDUCTION, multiplier=0.8))
        p2.add_status_effect(StatusEffect(StatusEffectType.DEFENSE_REDUCTION, multiplier=0.8))
        p2.add_status_effect(StatusEffect(StatusEffectType.BURN))

        self.assertLess(p1.current_hp, p1.max_hp)
        self.assertLess(p2.current_hp, p2.max_hp)
        self.assertLess(p1.effective_attack, p1.attack)
        self.assertLess(p2.effective_defense, p2.defense)
        self.assertTrue(p2.has_status_effect(StatusEffectType.BURN))

        # Register default objects including Pokemon Centers
        mgr = WorldInteractionManager(objects=create_default_world_objects())
        res = mgr.interact(self.player, "pokemon_center_meadow", (5.0, 5.0))

        self.assertTrue(res.success)
        self.assertEqual(res.interactable_type, InteractableType.POKEMON_CENTER)
        self.assertIn("restored", res.message.lower())

        # Verify full HP and restored stats
        self.assertEqual(p1.current_hp, p1.max_hp)
        self.assertEqual(p2.current_hp, p2.max_hp)
        self.assertEqual(p1.effective_attack, p1.attack)
        self.assertEqual(p2.effective_defense, p2.defense)
        self.assertEqual(len(p1.status_effects), 0)
        self.assertEqual(len(p2.status_effects), 0)

    def test_24_pokemon_center_at_every_world_region(self) -> None:
        """A Pokemon Center exists for each world region, located within that region's bounds."""
        from src.data.world_regions import create_default_world_regions
        regions = create_default_world_regions()
        self.assertEqual(len(regions), 7)

        default_objects = create_default_world_objects()
        centers = [obj for obj in default_objects if obj.interactable_type == InteractableType.POKEMON_CENTER]
        self.assertEqual(len(centers), 7)

        region_center_map: dict[str, Interactable] = {}
        for c in centers:
            self.assertIsNotNone(c.region_id)
            region_center_map[c.region_id] = c

        for reg in regions:
            self.assertIn(
                reg.region_id,
                region_center_map,
                f"Region '{reg.region_id}' must have a registered Pokemon Center.",
            )
            center = region_center_map[reg.region_id]
            self.assertTrue(
                reg.contains_point(center.position),
                f"Pokemon Center '{center.object_id}' position {center.position} must be within {reg.region_id} bounds {reg.bounds}.",
            )

    def test_25_pokemon_center_interaction_range_and_repeatability(self) -> None:
        """Pokemon Center validates range, never depletes, and can be used repeatedly."""
        mgr = WorldInteractionManager(objects=create_default_world_objects())

        # Out of range fails
        can_interact, reason = mgr.can_interact(self.player, "pokemon_center_meadow", (50.0, 50.0))
        self.assertFalse(can_interact)
        self.assertIn("out of range", reason.lower())

        # In range succeeds
        can_interact, reason = mgr.can_interact(self.player, "pokemon_center_meadow", (5.0, 5.0))
        self.assertTrue(can_interact)
        self.assertEqual(reason, "OK")

        # First use
        res1 = mgr.interact(self.player, "pokemon_center_meadow", (5.0, 5.0))
        self.assertTrue(res1.success)

        # Still available immediately afterwards (no depletion/cooldown)
        self.assertTrue(mgr.is_object_available("pokemon_center_meadow", self.player))
        res2 = mgr.interact(self.player, "pokemon_center_meadow", (5.0, 5.0))
        self.assertTrue(res2.success)


if __name__ == "__main__":
    unittest.main()
