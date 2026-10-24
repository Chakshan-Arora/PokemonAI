"""
Comprehensive test suite for Phase A: Quest Progression System.

Verifies:
- Objective tracking with current-count, target-count, and completion checks.
- Handling of incomplete objectives, remaining counts, and progress ratios.
- Multi-objective quest completion logic (all objectives must complete).
- Strict progress capping at target thresholds (no overflowing).
- Idempotent completion and reward claiming (no duplicate rewards).
- Save/load serialization and round-tripping of multi-objective quests.
- Backward compatibility with legacy save schemas.
- Event integration and direct progression APIs.
- Player convenience quest query methods.
"""
import copy
import json
import unittest

from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.inventory import Inventory
from src.models.quest import (
    ObjectiveType,
    QuestEventType,
    QuestObjective,
    QuestDefinition,
    ObjectiveProgress,
    QuestProgress,
    QuestStatus,
)
from src.models.quest_manager import QuestManager
from src.models.save_manager import SaveManager
from src.data.species import CHARMANDER, PIKACHU, SQUIRTLE
from src.data.attacks import TACKLE, SCRATCH
from src.data.quests import get_quest


class TestQuestProgressionSystem(unittest.TestCase):
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
        self.quest_mgr = QuestManager()
        self.save_mgr = SaveManager()

    def _create_pokemon(self, species=CHARMANDER, level=5) -> Pokemon:
        return Pokemon(
            species=species,
            personality=self.personality,
            level=level,
            experience=0,
            attacks=[TACKLE],
        )

    # --- 1. Objective Progress Tracking & Properties ---

    def test_01_objective_progress_properties_and_validation(self) -> None:
        """ObjectiveProgress correctly computes remaining, ratio, percentage, and validation."""
        obj = ObjectiveProgress(objective_id="catch_pidgey", target_count=5, current_count=2)
        self.assertEqual(obj.objective_id, "catch_pidgey")
        self.assertEqual(obj.target_count, 5)
        self.assertEqual(obj.current_count, 2)
        self.assertEqual(obj.remaining, 3)
        self.assertEqual(obj.remaining_count, 3)
        self.assertAlmostEqual(obj.progress_ratio, 0.4)
        self.assertAlmostEqual(obj.progress_percentage, 40.0)
        self.assertTrue(obj.is_incomplete)
        self.assertFalse(obj.is_completed)
        self.assertIn("2/5", repr(obj))

        # Test invalid constructors
        with self.assertRaises(ValueError):
            ObjectiveProgress(objective_id="", target_count=5)
        with self.assertRaises(ValueError):
            ObjectiveProgress(objective_id="valid", target_count=0)
        with self.assertRaises(TypeError):
            ObjectiveProgress(objective_id="valid", target_count=5, current_count="3")  # type: ignore

    def test_02_objective_progress_capping_and_bounds(self) -> None:
        """Progress strictly caps at target_count and ignores invalid mutation amounts."""
        obj = ObjectiveProgress(objective_id="obj_cap", target_count=10, current_count=0)

        # Increment below target
        changed = obj.increment(4)
        self.assertTrue(changed)
        self.assertEqual(obj.current_count, 4)
        self.assertEqual(obj.remaining, 6)

        # Increment past target - must clamp to target_count
        changed = obj.increment(100)
        self.assertTrue(changed)
        self.assertEqual(obj.current_count, 10)
        self.assertEqual(obj.remaining, 0)
        self.assertTrue(obj.is_completed)
        self.assertFalse(obj.is_incomplete)
        self.assertAlmostEqual(obj.progress_ratio, 1.0)
        self.assertAlmostEqual(obj.progress_percentage, 100.0)

        # Subsequent increment when already completed must return False and not overflow
        changed = obj.increment(5)
        self.assertFalse(changed)
        self.assertEqual(obj.current_count, 10)

        # set_progress clamping
        obj2 = ObjectiveProgress(objective_id="obj_set", target_count=8, current_count=2)
        obj2.set_progress(999)
        self.assertEqual(obj2.current_count, 8)
        self.assertTrue(obj2.is_completed)

        # set_progress cannot decrease progress or accept invalid inputs
        self.assertFalse(obj2.set_progress(5))
        self.assertEqual(obj2.current_count, 8)
        self.assertFalse(obj2.set_progress(-1))
        self.assertFalse(obj2.increment(0))
        self.assertFalse(obj2.increment(-2))

    # --- 2. Multi-Objective Quest Progression ---

    def test_03_multi_objective_quest_partial_and_full_completion(self) -> None:
        """A quest with multiple objectives is only completed when all objectives are complete."""
        # Define a custom 3-objective quest
        custom_quest = QuestDefinition(
            quest_id="tri_task",
            name="Tri Task Challenge",
            description="Complete three diverse objectives.",
            objectives=(
                QuestObjective(
                    objective_id="catch_pika",
                    objective_type=ObjectiveType.CAPTURE_SPECIES,
                    description="Capture 2 Pikachu",
                    target_count=2,
                    target_species="Pikachu",
                ),
                QuestObjective(
                    objective_id="defeat_mon",
                    objective_type=ObjectiveType.DEFEAT_ANY,
                    description="Defeat 3 Pokemon",
                    target_count=3,
                ),
                QuestObjective(
                    objective_id="collect_potions",
                    objective_type=ObjectiveType.COLLECT_ITEM,
                    description="Collect 5 Potions",
                    target_count=5,
                    target_item="potion",
                ),
            ),
            prerequisites=(),
            rewards={"antidote": 3},
        )
        catalog = {"tri_task": custom_quest}
        mgr = QuestManager(catalog=catalog)

        # Accept quest
        res = mgr.accept_quest(self.player, "tri_task")
        self.assertTrue(res.success)
        quest_prog = self.player.get_quest("tri_task")
        self.assertIsNotNone(quest_prog)
        self.assertEqual(quest_prog.total_objectives_count, 3)
        self.assertEqual(quest_prog.completed_objectives_count, 0)
        self.assertEqual(quest_prog.remaining_objectives_count, 3)
        self.assertFalse(quest_prog.is_completed)
        self.assertEqual(len(quest_prog.incomplete_objectives), 3)

        # Complete Objective 1
        mgr.advance_objective(self.player, "tri_task", "catch_pika", 2)
        self.assertTrue(quest_prog.is_objective_completed("catch_pika"))
        self.assertEqual(quest_prog.completed_objectives_count, 1)
        self.assertEqual(quest_prog.remaining_objectives_count, 2)
        self.assertFalse(quest_prog.is_completed)
        self.assertEqual(quest_prog.status, QuestStatus.ACTIVE)

        # Complete Objective 2
        mgr.advance_objective(self.player, "tri_task", "defeat_mon", 3)
        self.assertTrue(quest_prog.is_objective_completed("defeat_mon"))
        self.assertEqual(quest_prog.completed_objectives_count, 2)
        self.assertEqual(quest_prog.remaining_objectives_count, 1)
        self.assertFalse(quest_prog.is_completed)
        self.assertEqual(quest_prog.status, QuestStatus.ACTIVE)

        # Incomplete objectives list inspection
        incomplete = quest_prog.incomplete_objectives
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0].objective_id, "collect_potions")
        self.assertEqual(incomplete[0].remaining, 5)

        # Partially advance Objective 3
        mgr.advance_objective(self.player, "tri_task", "collect_potions", 4)
        self.assertEqual(quest_prog.get_objective("collect_potions").remaining, 1)
        self.assertFalse(quest_prog.is_completed)

        # Complete Objective 3 -> Quest must transition to COMPLETED
        mgr.advance_objective(self.player, "tri_task", "collect_potions", 1)
        self.assertTrue(quest_prog.is_objective_completed("collect_potions"))
        self.assertEqual(quest_prog.completed_objectives_count, 3)
        self.assertEqual(quest_prog.remaining_objectives_count, 0)
        self.assertTrue(quest_prog.is_completed)
        self.assertEqual(quest_prog.status, QuestStatus.COMPLETED)
        self.assertTrue(quest_prog.can_claim_rewards)

    def test_04_species_research_built_in_quest_progression(self) -> None:
        """Verify the built-in SPECIES_RESEARCH multi-objective quest progression."""
        # Unlock and accept species_research (requires first_encounter)
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        # Complete first_encounter
        self.quest_mgr.record_capture(self.player, "Pikachu", count=1)
        self.quest_mgr.claim_rewards(self.player, "first_encounter")

        # Now species_research is available
        self.assertEqual(self.quest_mgr.get_quest_status(self.player, "species_research"), QuestStatus.AVAILABLE)
        res = self.quest_mgr.accept_quest(self.player, "species_research")
        self.assertTrue(res.success)

        q = self.player.get_quest("species_research")
        self.assertIsNotNone(q)
        self.assertEqual(q.total_objectives_count, 2)

        # Capture 1 Pikachu via event helper
        self.quest_mgr.record_capture(self.player, "Pikachu", count=1)
        self.assertTrue(q.is_objective_completed("capture_pikachu"))
        self.assertFalse(q.is_objective_completed("capture_squirtle"))
        self.assertFalse(q.is_completed)

        # Capture Squirtle -> both objectives complete
        self.quest_mgr.record_capture(self.player, "Squirtle", count=1)
        self.assertTrue(q.is_objective_completed("capture_squirtle"))
        self.assertTrue(q.is_completed)
        self.assertEqual(q.status, QuestStatus.COMPLETED)

    # --- 3. Event-Driven Item Matching & Non-Interference ---

    def test_05_item_collected_events_guard_against_mismatched_items(self) -> None:
        """ITEM_COLLECTED events only update objectives targeting the specified item."""
        custom_quest = QuestDefinition(
            quest_id="potion_hunt",
            name="Potion Hunt",
            description="Collect 3 potions.",
            objectives=(
                QuestObjective(
                    objective_id="need_potions",
                    objective_type=ObjectiveType.COLLECT_ITEM,
                    description="Collect 3 potions",
                    target_count=3,
                    target_item="potion",
                ),
            ),
            prerequisites=(),
            rewards={"antidote": 1},
        )
        mgr = QuestManager(catalog={"potion_hunt": custom_quest})
        mgr.accept_quest(self.player, "potion_hunt")
        q = self.player.get_quest("potion_hunt")

        # Player collects an unrelated item (e.g. antidote)
        self.player.inventory.add_item("antidote", 5)
        mgr.record_item_collected(self.player, item_id="antidote")
        # Objective progress must NOT change
        self.assertEqual(q.get_objective("need_potions").current_count, 0)
        self.assertEqual(q.get_objective("need_potions").remaining, 3)

        # Player collects potion
        self.player.inventory.add_item("potion", 2)
        mgr.record_item_collected(self.player, item_id="potion")
        self.assertEqual(q.get_objective("need_potions").current_count, 2)
        self.assertEqual(q.get_objective("need_potions").remaining, 1)
        self.assertFalse(q.is_completed)

        # Player collects 1 more potion
        self.player.inventory.add_item("potion", 1)
        mgr.record_item_collected(self.player, item_id="potion")
        self.assertEqual(q.get_objective("need_potions").current_count, 3)
        self.assertTrue(q.is_completed)

    # --- 4. Idempotent Completion & Anti-Duplication ---

    def test_06_idempotent_quest_completion_and_reward_claiming(self) -> None:
        """Repeated events or claim calls never re-trigger completion or duplicate rewards."""
        custom_quest = QuestDefinition(
            quest_id="idempotent_test",
            name="Idempotent Test",
            description="Catch 1 Pikachu",
            objectives=(
                QuestObjective(
                    objective_id="obj_pika",
                    objective_type=ObjectiveType.CAPTURE_SPECIES,
                    description="Catch 1 Pikachu",
                    target_count=1,
                    target_species="Pikachu",
                ),
            ),
            prerequisites=(),
            rewards={"potion": 2},
        )
        mgr = QuestManager(catalog={"idempotent_test": custom_quest})
        mgr.accept_quest(self.player, "idempotent_test")
        q = self.player.get_quest("idempotent_test")

        # First capture completes the quest
        res1 = mgr.record_capture(self.player, "Pikachu", count=1, event_id="evt_001")
        self.assertEqual(res1.quests_completed, ["idempotent_test"])
        self.assertTrue(q.is_completed)
        self.assertEqual(q.status, QuestStatus.COMPLETED)

        # Replaying event with same event_id is ignored
        res_replay = mgr.record_capture(self.player, "Pikachu", count=1, event_id="evt_001")
        self.assertEqual(res_replay.events_processed, 0)
        self.assertEqual(res_replay.objectives_updated, 0)

        # Subsequent different event on completed quest does not report newly completed
        res2 = mgr.record_capture(self.player, "Pikachu", count=1, event_id="evt_002")
        self.assertEqual(res2.quests_completed, [])
        self.assertEqual(q.get_objective("obj_pika").current_count, 1)

        # Claim rewards first time
        initial_potions = self.player.inventory.get_quantity("potion")
        claim1 = mgr.claim_rewards(self.player, "idempotent_test")
        self.assertTrue(claim1.success)
        self.assertEqual(claim1.items_granted, {"potion": 2})
        self.assertEqual(self.player.inventory.get_quantity("potion"), initial_potions + 2)
        self.assertTrue(q.rewards_claimed)
        self.assertFalse(q.can_claim_rewards)

        # Claim rewards second time (must fail cleanly and grant 0 items)
        claim2 = mgr.claim_rewards(self.player, "idempotent_test")
        self.assertFalse(claim2.success)
        self.assertEqual(claim2.items_granted, {})
        self.assertEqual(self.player.inventory.get_quantity("potion"), initial_potions + 2)

    # --- 5. Direct Progression APIs & State Evaluation ---

    def test_07_direct_objective_manipulation_apis(self) -> None:
        """advance_objective, set_objective_progress, and evaluate_state_based_objectives."""
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        q = self.player.get_quest("first_encounter")

        # advance_objective
        adv = self.quest_mgr.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)
        self.assertTrue(adv)
        self.assertTrue(q.is_completed)

        # Re-advancing an already completed objective returns False
        self.assertFalse(self.quest_mgr.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1))

        # set_objective_progress on non-existent or locked quest
        self.assertFalse(self.quest_mgr.set_objective_progress(self.player, "nonexistent", "obj", 1))

        # evaluate_state_based_objectives
        # Player has 3 potions and a level 5 Charmander
        self.player.inventory.add_item("potion", 3)
        starter_mon = self._create_pokemon(species=CHARMANDER, level=5)
        self.player.add_pokemon(starter_mon)

        # Accept growing_stronger (requires level 5 Pokemon)
        # Note: growing_stronger requires first_encounter (which was completed above!)
        self.quest_mgr.claim_rewards(self.player, "first_encounter")
        self.quest_mgr.accept_quest(self.player, "growing_stronger")
        # Immediate state evaluation should have completed it upon acceptance!
        self.assertTrue(self.player.is_quest_completed("growing_stronger"))

    def test_08_player_convenience_methods(self) -> None:
        """Player helper methods: get_quest, has_quest, is_quest_completed, is_quest_active."""
        self.assertFalse(self.player.has_quest("first_encounter"))
        self.assertIsNone(self.player.get_quest("first_encounter"))
        self.assertFalse(self.player.is_quest_completed("first_encounter"))
        self.assertFalse(self.player.is_quest_active("first_encounter"))

        # Accept quest
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        self.assertTrue(self.player.has_quest("first_encounter"))
        self.assertIsNotNone(self.player.get_quest("first_encounter"))
        self.assertTrue(self.player.is_quest_active("first_encounter"))
        self.assertFalse(self.player.is_quest_completed("first_encounter"))

        # Advance to completion
        self.quest_mgr.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)
        self.assertTrue(self.player.is_quest_completed("first_encounter"))
        self.assertFalse(self.player.is_quest_active("first_encounter"))

    # --- 6. Save/Load Round-Tripping & Backward Compatibility ---

    def test_09_save_load_round_trip_preserves_multi_objective_progress(self) -> None:
        """Save and reload correctly serializes all objective states and progress counts."""
        custom_quest = QuestDefinition(
            quest_id="save_test_quest",
            name="Save Test Quest",
            description="Testing serialization of multi-objective quests.",
            objectives=(
                QuestObjective(
                    objective_id="obj_a",
                    objective_type=ObjectiveType.CAPTURE_ANY,
                    description="Capture 5 Pokemon",
                    target_count=5,
                ),
                QuestObjective(
                    objective_id="obj_b",
                    objective_type=ObjectiveType.DEFEAT_ANY,
                    description="Defeat 3 Pokemon",
                    target_count=3,
                ),
            ),
            prerequisites=(),
            rewards={"potion": 1},
        )
        mgr = QuestManager(catalog={"save_test_quest": custom_quest})
        mgr.accept_quest(self.player, "save_test_quest")
        mgr.advance_objective(self.player, "save_test_quest", "obj_a", 3)
        mgr.advance_objective(self.player, "save_test_quest", "obj_b", 3)  # obj_b is completed, obj_a is partial

        # Serialize
        payload = self.save_mgr.serialize(self.player)
        deserialized_player = self.save_mgr.deserialize(payload, quest_catalog={"save_test_quest": custom_quest})

        # Inspect restored quest
        restored_q = deserialized_player.get_quest("save_test_quest")
        self.assertIsNotNone(restored_q)
        self.assertFalse(restored_q.is_completed)
        self.assertEqual(restored_q.status, QuestStatus.ACTIVE)

        obj_a = restored_q.get_objective("obj_a")
        self.assertIsNotNone(obj_a)
        self.assertEqual(obj_a.current_count, 3)
        self.assertEqual(obj_a.target_count, 5)
        self.assertEqual(obj_a.remaining, 2)
        self.assertFalse(obj_a.is_completed)

        obj_b = restored_q.get_objective("obj_b")
        self.assertIsNotNone(obj_b)
        self.assertEqual(obj_b.current_count, 3)
        self.assertEqual(obj_b.target_count, 3)
        self.assertEqual(obj_b.remaining, 0)
        self.assertTrue(obj_b.is_completed)

        # Save -> Load -> Save round-trip produces identical JSON payload (excluding saved_at timestamp)
        second_payload = self.save_mgr.serialize(deserialized_player)
        p1_copy = copy.deepcopy(payload)
        p2_copy = copy.deepcopy(second_payload)
        p1_copy.pop("saved_at", None)
        p2_copy.pop("saved_at", None)
        self.assertEqual(p1_copy, p2_copy)

    def test_10_backward_compatibility_with_schema_v1_and_missing_objectives(self) -> None:
        """Legacy schemas without quests or missing objective entries restore cleanly."""
        # Schema v1 payload (no quests, no treasures, no discoveries)
        v1_payload = {
            "schema_version": 1,
            "player": {
                "unique_id": "v1_player",
                "name": "Red",
                "created_at": 1000.0,
            },
            "inventory": {
                "capacity": 20,
                "slots": {},
            },
            "collection": [],
            "team": [],
            "active_pokemon_id": None,
        }
        p = self.save_mgr.deserialize(v1_payload)
        self.assertEqual(p.name, "Red")
        self.assertEqual(len(p.quests), 0)
        self.assertFalse(p.has_quest("first_encounter"))

        # Payload where a quest definition has 2 objectives, but save payload only has 1
        v4_partial = {
            "schema_version": 4,
            "player": {
                "unique_id": "v4_partial",
                "name": "Blue",
                "created_at": 2000.0,
            },
            "inventory": {"capacity": 20, "slots": {}},
            "collection": [],
            "team": [],
            "active_pokemon_id": None,
            "collected_treasures": [],
            "discovered_regions": [],
            "discovered_landmarks": [],
            "quests": {
                "species_research": {
                    "status": "ACTIVE",
                    "is_completed": False,
                    "rewards_claimed": False,
                    "objective_progress": {
                        "capture_pikachu": {
                            "target_count": 1,
                            "current_count": 1,
                            "is_completed": True,
                        }
                        # "capture_squirtle" is missing in saved payload
                    },
                }
            },
        }
        p2 = self.save_mgr.deserialize(v4_partial)
        q2 = p2.get_quest("species_research")
        self.assertIsNotNone(q2)
        # Missing objective should be initialized with 0 defaults
        self.assertEqual(q2.get_objective("capture_pikachu").current_count, 1)
        self.assertIsNotNone(q2.get_objective("capture_squirtle"))
        self.assertEqual(q2.get_objective("capture_squirtle").current_count, 0)
        self.assertEqual(q2.get_objective("capture_squirtle").remaining, 1)
        self.assertFalse(q2.is_completed)


if __name__ == "__main__":
    unittest.main()
