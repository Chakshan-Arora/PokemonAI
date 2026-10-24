"""
Unit tests for the Quest & Objective System subsystem.
Verifies quest definitions, objective validation, prerequisite evaluation,
gameplay event processing across all 7 objective types, deduplication,
atomic reward delivery, capacity limits, player isolation, and save/load persistence.
"""
import unittest
import tempfile
from pathlib import Path

from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.inventory import Inventory
from src.models.personality import Personality
from src.models.save_data import CURRENT_SCHEMA_VERSION, SaveDataError
from src.models.save_manager import (
    serialize_player,
    deserialize_player,
    save_game,
    load_game,
)
from src.models.quest import (
    QuestStatus,
    ObjectiveType,
    QuestEventType,
    QuestObjective,
    QuestDefinition,
    ObjectiveProgress,
    QuestProgress,
    QuestEvent,
)
from src.models.quest_manager import (
    QuestManager,
    QuestActionResult,
    EventResult,
    QuestRewardResult,
)
from src.data.quests import (
    FIRST_ENCOUNTER,
    SPECIES_RESEARCH,
    GROWING_STRONGER,
    COLLECTORS_PRIDE,
    WILD_CHALLENGER,
    STOCKING_SUPPLIES,
    QUEST_CATALOG,
    get_quest,
    list_catalog_quests,
)
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import TACKLE, SCRATCH


class TestQuestManager(unittest.TestCase):
    """
    Exhaustive test suite for quest management, progress tracking, and persistence.
    """

    def setUp(self) -> None:
        self.personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )
        self.player = Player(name="Ash")
        self.manager = QuestManager()

    def _create_pokemon(self, species, level=5) -> Pokemon:
        return Pokemon(
            species=species,
            personality=self.personality,
            level=level,
            experience=0,
            attacks=[TACKLE],
        )

    # --- 1. Model & Definition Validation Tests ---

    def test_01_objective_validation(self) -> None:
        """QuestObjective validates IDs, types, counts, species, and item requirements."""
        # Valid objective
        obj = QuestObjective(
            objective_id="test_obj",
            objective_type=ObjectiveType.CAPTURE_ANY,
            description="Test capture",
            target_count=2,
        )
        self.assertEqual(obj.objective_id, "test_obj")
        self.assertEqual(obj.target_count, 2)

        # Invalid target_count
        with self.assertRaises(ValueError):
            QuestObjective(
                objective_id="bad_count",
                objective_type=ObjectiveType.CAPTURE_ANY,
                description="Bad",
                target_count=0,
            )

        # Missing target_species for species-specific objective
        with self.assertRaises(ValueError):
            QuestObjective(
                objective_id="no_species",
                objective_type=ObjectiveType.CAPTURE_SPECIES,
                description="Need species",
                target_count=1,
            )

        # Missing target_item for item-specific objective
        with self.assertRaises(ValueError):
            QuestObjective(
                objective_id="no_item",
                objective_type=ObjectiveType.COLLECT_ITEM,
                description="Need item",
                target_count=1,
            )

        # Level exceeding max 100
        with self.assertRaises(ValueError):
            QuestObjective(
                objective_id="lvl_over",
                objective_type=ObjectiveType.REACH_LEVEL,
                description="Over 100",
                target_count=101,
            )

    def test_02_quest_definition_validation(self) -> None:
        """QuestDefinition enforces unique objective IDs, non-empty objectives, and valid rewards."""
        valid_obj = QuestObjective(
            objective_id="obj_1",
            objective_type=ObjectiveType.CAPTURE_ANY,
            description="Desc",
        )
        # Duplicate objective ID rejection
        with self.assertRaises(ValueError):
            QuestDefinition(
                quest_id="dup_quest",
                name="Duplicate",
                description="Desc",
                objectives=(valid_obj, valid_obj),
            )

        # Empty objectives sequence rejection
        with self.assertRaises(ValueError):
            QuestDefinition(
                quest_id="empty_quest",
                name="Empty",
                description="Desc",
                objectives=(),
            )

        # Invalid reward quantity
        with self.assertRaises(ValueError):
            QuestDefinition(
                quest_id="bad_reward",
                name="Bad Reward",
                description="Desc",
                objectives=(valid_obj,),
                rewards={"potion": 0},
            )

    def test_03_objective_progress_mutation(self) -> None:
        """ObjectiveProgress correctly tracks, clamps, and completes progress."""
        prog = ObjectiveProgress(objective_id="p1", target_count=5, current_count=0)
        self.assertFalse(prog.is_completed)

        # Increment
        self.assertTrue(prog.increment(2))
        self.assertEqual(prog.current_count, 2)
        self.assertFalse(prog.is_completed)

        # Increment past target caps at target_count
        self.assertTrue(prog.increment(10))
        self.assertEqual(prog.current_count, 5)
        self.assertTrue(prog.is_completed)

        # Further increments return False
        self.assertFalse(prog.increment(1))

        # set_progress
        prog2 = ObjectiveProgress(objective_id="p2", target_count=10)
        self.assertTrue(prog2.set_progress(7))
        self.assertEqual(prog2.current_count, 7)
        self.assertFalse(prog2.set_progress(5))  # setting lower does not regress

    # --- 2. Quest Availability & Prerequisites ---

    def test_04_initial_quest_availability(self) -> None:
        """Quests without prerequisites are AVAILABLE; dependent quests are LOCKED."""
        # first_encounter has no prerequisites
        self.assertEqual(
            self.manager.get_quest_status(self.player, "first_encounter"),
            QuestStatus.AVAILABLE,
        )
        # species_research requires first_encounter
        self.assertEqual(
            self.manager.get_quest_status(self.player, "species_research"),
            QuestStatus.LOCKED,
        )

        available = self.manager.list_available_quests(self.player)
        available_ids = [q.quest_id for q in available]
        self.assertIn("first_encounter", available_ids)
        self.assertIn("collectors_pride", available_ids)
        self.assertNotIn("species_research", available_ids)

    def test_05_prerequisite_completion_unlocks_dependent_quests(self) -> None:
        """Completing a prerequisite quest unlocks downstream quests."""
        # Accept and complete first_encounter
        self.manager.accept_quest(self.player, "first_encounter")
        self.manager.record_capture(self.player, "Pikachu")
        self.assertEqual(
            self.manager.get_quest_status(self.player, "first_encounter"),
            QuestStatus.COMPLETED,
        )

        # Now species_research and growing_stronger should be AVAILABLE
        self.assertEqual(
            self.manager.get_quest_status(self.player, "species_research"),
            QuestStatus.AVAILABLE,
        )
        self.assertEqual(
            self.manager.get_quest_status(self.player, "growing_stronger"),
            QuestStatus.AVAILABLE,
        )

    # --- 3. Acceptance & Immediate State Evaluation ---

    def test_06_quest_acceptance_lifecycle(self) -> None:
        """Accepting a quest moves it to ACTIVE and rejects duplicate acceptance."""
        res = self.manager.accept_quest(self.player, "first_encounter")
        self.assertTrue(res.success)
        self.assertEqual(
            self.manager.get_quest_status(self.player, "first_encounter"),
            QuestStatus.ACTIVE,
        )

        # Duplicate acceptance rejected
        res2 = self.manager.accept_quest(self.player, "first_encounter")
        self.assertFalse(res2.success)
        self.assertIn("already active", res2.message.lower())

        # Accepting locked quest rejected
        res_locked = self.manager.accept_quest(self.player, "species_research")
        self.assertFalse(res_locked.success)
        self.assertIn("prerequisites not met", res_locked.message.lower())

    def test_07_immediate_state_evaluation_on_acceptance(self) -> None:
        """Quests evaluate existing collection and inventory upon acceptance."""
        # Player already owns Charmander and 3 Potions
        charmander = self._create_pokemon(CHARMANDER, level=6)
        self.player.add_pokemon(charmander)
        self.player.inventory.add_item("potion", 3)

        # Accept collector's pride (own 1 Charmander) -> immediately completes
        res1 = self.manager.accept_quest(self.player, "collectors_pride")
        self.assertTrue(res1.success)
        self.assertEqual(
            self.manager.get_quest_status(self.player, "collectors_pride"),
            QuestStatus.COMPLETED,
        )

        # Accept stocking supplies (possess 3 Potions) -> immediately completes
        res2 = self.manager.accept_quest(self.player, "stocking_supplies")
        self.assertTrue(res2.success)
        self.assertEqual(
            self.manager.get_quest_status(self.player, "stocking_supplies"),
            QuestStatus.COMPLETED,
        )

    # --- 4. Event Processing Across All 7 Objective Types ---

    def test_08_capture_any_objective(self) -> None:
        """CAPTURE_ANY increments progress regardless of captured species."""
        self.manager.accept_quest(self.player, "first_encounter")
        res = self.manager.record_capture(self.player, "Rattata")

        self.assertEqual(res.events_processed, 1)
        self.assertEqual(res.objectives_updated, 1)
        self.assertIn("first_encounter", res.quests_completed)
        self.assertEqual(
            self.manager.get_quest_status(self.player, "first_encounter"),
            QuestStatus.COMPLETED,
        )

    def test_09_capture_species_objective(self) -> None:
        """CAPTURE_SPECIES only advances when target species is captured."""
        # Complete first_encounter to unlock species_research
        self.manager.accept_quest(self.player, "first_encounter")
        self.manager.record_capture(self.player, "Pidgey")
        self.manager.accept_quest(self.player, "species_research")

        # Capture wrong species -> 0 objectives updated
        res_wrong = self.manager.record_capture(self.player, "Charmander")
        self.assertEqual(res_wrong.objectives_updated, 0)

        # Capture Pikachu -> 1 objective updated
        res_pika = self.manager.record_capture(self.player, "Pikachu")
        self.assertEqual(res_pika.objectives_updated, 1)
        self.assertEqual(len(res_pika.quests_completed), 0)

        # Capture Squirtle -> 1 objective updated and quest completes
        res_sq = self.manager.record_capture(self.player, "Squirtle")
        self.assertEqual(res_sq.objectives_updated, 1)
        self.assertIn("species_research", res_sq.quests_completed)
        self.assertEqual(
            self.manager.get_quest_status(self.player, "species_research"),
            QuestStatus.COMPLETED,
        )

    def test_10_defeat_any_objective(self) -> None:
        """DEFEAT_ANY advances upon defeating any Pokemon."""
        self.manager.accept_quest(self.player, "wild_challenger")
        res = self.manager.record_defeat(self.player, "Geodude")

        self.assertEqual(res.objectives_updated, 1)
        self.assertIn("wild_challenger", res.quests_completed)
        self.assertEqual(
            self.manager.get_quest_status(self.player, "wild_challenger"),
            QuestStatus.COMPLETED,
        )

    def test_11_reach_level_objective(self) -> None:
        """REACH_LEVEL tracks level ups and reflects highest Pokemon level."""
        # Complete first_encounter to unlock growing_stronger
        self.manager.accept_quest(self.player, "first_encounter")
        self.manager.record_capture(self.player, "Pikachu")

        self.manager.accept_quest(self.player, "growing_stronger")
        pika = self._create_pokemon(PIKACHU, level=3)
        self.player.add_pokemon(pika)

        # Level up to 4 -> updates progress to 4, does not complete
        res1 = self.manager.record_level_up(self.player, new_level=4)
        self.assertEqual(res1.objectives_updated, 1)
        self.assertEqual(len(res1.quests_completed), 0)

        # Level up to 5 -> completes quest
        from src.models.progression import apply_experience
        apply_experience(pika, 2000)
        self.assertGreaterEqual(pika.level, 5)
        res2 = self.manager.record_level_up(self.player, new_level=pika.level)
        self.assertEqual(res2.objectives_updated, 1)
        self.assertIn("growing_stronger", res2.quests_completed)
        self.assertEqual(
            self.manager.get_quest_status(self.player, "growing_stronger"),
            QuestStatus.COMPLETED,
        )

    def test_12_own_species_objective(self) -> None:
        """OWN_SPECIES updates when Pokemon is added to player collection."""
        self.manager.accept_quest(self.player, "collectors_pride")
        q_prog = self.manager.get_quest_progress(self.player, "collectors_pride")
        self.assertEqual(q_prog.status, QuestStatus.ACTIVE)

        # Add Charmander to collection
        charm = self._create_pokemon(CHARMANDER)
        self.player.add_pokemon(charm)

        res = self.manager.record_event(
            self.player,
            QuestEventType.POKEMON_COLLECTED,
            payload={"species_name": "Charmander"},
        )
        self.assertEqual(res.objectives_updated, 1)
        self.assertIn("collectors_pride", res.quests_completed)

    def test_13_collect_item_objective(self) -> None:
        """COLLECT_ITEM tracks accumulated inventory quantity."""
        self.manager.accept_quest(self.player, "stocking_supplies")

        # Add 2 potions
        self.player.inventory.add_item("potion", 2)
        res1 = self.manager.record_item_collected(self.player, "potion")
        self.assertEqual(res1.objectives_updated, 1)
        self.assertEqual(len(res1.quests_completed), 0)

        # Add 1 more potion
        self.player.inventory.add_item("potion", 1)
        res2 = self.manager.record_item_collected(self.player, "potion")
        self.assertEqual(res2.objectives_updated, 1)
        self.assertIn("stocking_supplies", res2.quests_completed)

    # --- 5. Event Deduplication & Safety ---

    def test_14_event_deduplication(self) -> None:
        """Events with identical event_id are processed once and ignored subsequently."""
        self.manager.accept_quest(self.player, "first_encounter")

        # First dispatch with event_id
        res1 = self.manager.record_capture(self.player, "Pikachu", event_id="evt_001")
        self.assertEqual(res1.events_processed, 1)
        self.assertEqual(res1.objectives_updated, 1)

        # Duplicate dispatch with identical event_id
        res2 = self.manager.record_capture(self.player, "Pikachu", event_id="evt_001")
        self.assertEqual(res2.events_processed, 0)
        self.assertIn("duplicate", res2.message.lower())

    def test_15_invalid_event_type_handled_safely(self) -> None:
        """Invalid event types do not raise unhandled exceptions."""
        res = self.manager.record_event(self.player, "invalid_nonexistent_event")
        self.assertEqual(res.events_processed, 0)
        self.assertIn("unknown event type", res.message.lower())

    # --- 6. Atomic Reward Delivery & Capacity Limits ---

    def test_16_atomic_reward_claiming(self) -> None:
        """Claiming rewards delivers items, marks quest claimed, and rejects duplicate claims."""
        self.manager.accept_quest(self.player, "first_encounter")
        self.manager.record_capture(self.player, "Pikachu")

        # Claim rewards (first_encounter grants 2 potions)
        claim_res = self.manager.claim_rewards(self.player, "first_encounter")
        self.assertTrue(claim_res.success)
        self.assertEqual(claim_res.items_granted, {"potion": 2})
        self.assertEqual(self.player.inventory.get_quantity("potion"), 2)

        q_prog = self.manager.get_quest_progress(self.player, "first_encounter")
        self.assertTrue(q_prog.rewards_claimed)

        # Duplicate claim is rejected
        dup_res = self.manager.claim_rewards(self.player, "first_encounter")
        self.assertFalse(dup_res.success)
        self.assertIn("already been claimed", dup_res.message.lower())
        # Inventory quantity unchanged
        self.assertEqual(self.player.inventory.get_quantity("potion"), 2)

    def test_17_cannot_claim_rewards_before_completion(self) -> None:
        """Claiming rewards on an active uncompleted quest is rejected."""
        self.manager.accept_quest(self.player, "first_encounter")
        res = self.manager.claim_rewards(self.player, "first_encounter")
        self.assertFalse(res.success)
        self.assertIn("not completed", res.message.lower())

    def test_18_reward_delivery_fails_atomically_on_capacity_limit(self) -> None:
        """If inventory is full, rewards are not granted and rewards_claimed remains False."""
        # Create a player with 1 inventory slot capacity
        small_inv = Inventory(capacity=1)
        small_inv.add_item("antidote", 1)  # Fill slot 1 of 1
        player = Player(name="Constrained", inventory=small_inv)

        self.manager.accept_quest(player, "first_encounter")
        self.manager.record_capture(player, "Pikachu")

        # first_encounter rewards {"potion": 2}, requiring a new slot
        claim_res = self.manager.claim_rewards(player, "first_encounter")
        self.assertFalse(claim_res.success)
        self.assertIn("capacity exceeded", claim_res.message.lower())

        # Inventory remains untouched
        self.assertEqual(player.inventory.slots_used, 1)
        self.assertEqual(player.inventory.get_quantity("potion"), 0)

        # rewards_claimed flag is still False
        q_prog = self.manager.get_quest_progress(player, "first_encounter")
        self.assertFalse(q_prog.rewards_claimed)

    # --- 7. Player Quest Isolation ---

    def test_19_player_quest_isolation(self) -> None:
        """Quest progress for one player does not mutate or affect another player."""
        player_b = Player(name="Gary")

        self.manager.accept_quest(self.player, "first_encounter")
        self.manager.record_capture(self.player, "Pikachu")

        self.assertEqual(
            self.manager.get_quest_status(self.player, "first_encounter"),
            QuestStatus.COMPLETED,
        )
        self.assertEqual(
            self.manager.get_quest_status(player_b, "first_encounter"),
            QuestStatus.AVAILABLE,
        )
        self.assertNotIn("first_encounter", player_b.quests)

    # --- 8. Save/Load Persistence (Schema v2) & Migration (v1) ---

    def test_20_quest_save_load_round_trip(self) -> None:
        """Quest progress, objectives, and reward claim status survive serialization round-trip."""
        # Accept first_encounter, complete it, and claim rewards
        self.manager.accept_quest(self.player, "first_encounter")
        self.manager.record_capture(self.player, "Pikachu")
        self.manager.claim_rewards(self.player, "first_encounter")

        # Accept wild_challenger (ACTIVE, 0 progress)
        self.manager.accept_quest(self.player, "wild_challenger")

        # Serialize player
        save_data = serialize_player(self.player)
        self.assertEqual(save_data["schema_version"], CURRENT_SCHEMA_VERSION)
        self.assertIn("quests", save_data)
        self.assertIn("first_encounter", save_data["quests"])
        self.assertIn("wild_challenger", save_data["quests"])

        # Deserialize into new Player
        restored = deserialize_player(save_data)
        self.assertEqual(restored.name, "Ash")
        self.assertEqual(len(restored.quests), 2)

        # Assert first_encounter restored state
        q1 = restored.quests["first_encounter"]
        self.assertEqual(q1.status, QuestStatus.COMPLETED)
        self.assertTrue(q1.is_completed)
        self.assertTrue(q1.rewards_claimed)

        # Assert wild_challenger restored state
        q2 = restored.quests["wild_challenger"]
        self.assertEqual(q2.status, QuestStatus.ACTIVE)
        self.assertFalse(q2.is_completed)
        self.assertFalse(q2.rewards_claimed)

        # Continuing quest progress on restored player works seamlessly
        self.manager.record_defeat(restored, "Pidgey")
        self.assertEqual(
            self.manager.get_quest_status(restored, "wild_challenger"),
            QuestStatus.COMPLETED,
        )

    def test_21_schema_v1_save_migration(self) -> None:
        """Schema version 1 saves without quests migrate cleanly to empty quest state."""
        # Simulate a valid v1 save payload without 'quests' section
        v1_data = {
            "schema_version": 1,
            "player": {"name": "Red", "unique_id": "red-001", "max_team_size": 6},
            "inventory": {"capacity": 20, "items": {"potion": 5}},
            "collection": [],
            "team": [],
            "active_pokemon_id": None,
        }

        # Deserialization must succeed via backward-compatible migration
        migrated_player = deserialize_player(v1_data)
        self.assertEqual(migrated_player.name, "Red")
        self.assertEqual(migrated_player.quests, {})

        # Player can now interact with quests normally
        self.assertEqual(
            self.manager.get_quest_status(migrated_player, "first_encounter"),
            QuestStatus.AVAILABLE,
        )
        act = self.manager.accept_quest(migrated_player, "first_encounter")
        self.assertTrue(act.success)

    def test_22_corrupt_quest_save_data_rejected(self) -> None:
        """Corrupt or unknown quest data in save payload raises SaveDataError."""
        valid_data = serialize_player(self.player)

        # Unknown quest ID
        bad_quest = dict(valid_data)
        bad_quest["quests"] = {
            "unknown_quest_xyz": {
                "quest_id": "unknown_quest_xyz",
                "status": "active",
                "is_completed": False,
                "rewards_claimed": False,
                "objective_progress": {},
            }
        }
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(bad_quest)
        self.assertIn("unknown quest", str(ctx.exception).lower())

        # Unknown objective ID
        bad_obj = dict(valid_data)
        bad_obj["quests"] = {
            "first_encounter": {
                "quest_id": "first_encounter",
                "status": "active",
                "is_completed": False,
                "rewards_claimed": False,
                "objective_progress": {
                    "nonexistent_obj": {"current_count": 1}
                },
            }
        }
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(bad_obj)
        self.assertIn("unknown objective", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
