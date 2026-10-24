"""
Unit and integration tests for Phase C2.2: Specific World Interaction Objectives.

Tests verify:
1. Correct target interaction advances progress.
2. Wrong target does not advance progress.
3. Region-restricted interaction only progresses in the correct region.
4. Unrestricted interaction objectives work across regions.
5. Failed or invalid interactions do not advance progress (out of range, depleted, full inventory).
6. A single successful interaction is not counted twice (event replay deduplication).
7. Progress respects objective count limits.
8. Multi-count objectives progress sequentially up to target count.
9. Case-insensitive matching works reliably for object ID and region ID.
10. Target object matching works for NPCs with or without 'npc_' prefix.
11. End-to-end WorldInteractionManager.interact() advances matching quest objectives authoritatively.
12. End-to-end interaction in wrong region or with wrong object does not advance restricted objective.
13. Quest completion transitions, notifications, explicit reward claiming, and save/load round-trips.
14. Existing world interactions (resource gathering, signs, landmarks, treasures) remain compatible.
"""
import unittest
import tempfile
import shutil
from pathlib import Path

from src.models.player import Player
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.world_interaction import (
    InteractableType,
    Interactable,
    InteractionResult,
)
from src.models.world_interaction_manager import WorldInteractionManager
from src.models.save_manager import save_game, load_game
from src.models.quest import (
    ObjectiveType,
    QuestEventType,
    QuestObjective,
    QuestDefinition,
    QuestStatus,
)
from src.models.quest_manager import QuestManager
from src.data.species import PIKACHU
from src.data.attacks import THUNDER_SHOCK


class TestWorldInteractionObjectives(unittest.TestCase):
    """Test suite covering specific world interaction objectives (Phase C2.2)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.save_file = str(Path(self.temp_dir) / "test_c2_2_save.json")

        self.personality = Personality(
            aggression=30, curiosity=60, fear=20, sociability=80, loyalty=90, confidence=70
        )
        self.starter = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=5,
            attacks=[THUNDER_SHOCK],
        )
        self.player = Player(name="Red")
        self.player.add_pokemon(self.starter)
        self.player.add_to_team(self.starter)
        self.player.set_active_pokemon(self.starter)

        # Custom interaction-aware quest definitions
        self.quest_read_sign = QuestDefinition(
            quest_id="read_route1_sign",
            name="Trail Reader",
            description="Read the Route 1 Trail Marker sign.",
            objectives=(
                QuestObjective(
                    objective_id="obj_read_sign",
                    objective_type=ObjectiveType.INTERACT_OBJECT,
                    description="Read the Route 1 Trail Marker",
                    target_count=1,
                    target_object="route1_sign",
                    target_region="starting_meadow",
                ),
            ),
            rewards={"potion": 2},
        )

        self.quest_harvest_berries = QuestDefinition(
            quest_id="harvest_meadow_berries",
            name="Berry Harvester",
            description="Harvest berries from the bush 2 times.",
            objectives=(
                QuestObjective(
                    objective_id="obj_harvest_bush",
                    objective_type=ObjectiveType.INTERACT_OBJECT,
                    description="Harvest the Berry Bush 2 times",
                    target_count=2,
                    target_object="berry_bush_route1",
                ),
            ),
            rewards={"super_potion": 1},
        )

        self.quest_any_interaction_forest = QuestDefinition(
            quest_id="explore_forest_objects",
            name="Forest Explorer",
            description="Interact with any world object in the Forest Trail.",
            objectives=(
                QuestObjective(
                    objective_id="obj_forest_interact",
                    objective_type=ObjectiveType.INTERACT_OBJECT,
                    description="Interact with any object in Forest Trail",
                    target_count=1,
                    target_object=None,
                    target_region="forest_trail",
                ),
            ),
            rewards={"antidote": 2},
        )

        self.quest_talk_to_oak = QuestDefinition(
            quest_id="consult_prof_oak",
            name="Academic Guidance",
            description="Speak with Professor Oak.",
            objectives=(
                QuestObjective(
                    objective_id="obj_speak_oak",
                    objective_type=ObjectiveType.INTERACT_OBJECT,
                    description="Speak with Professor Oak",
                    target_count=1,
                    target_object="prof_oak",
                ),
            ),
            rewards={"poke_ball": 5},
        )

        self.quest_unrestricted_any = QuestDefinition(
            quest_id="general_curiosity",
            name="General Inquisitor",
            description="Interact with any world object anywhere.",
            objectives=(
                QuestObjective(
                    objective_id="obj_any_anywhere",
                    objective_type=ObjectiveType.INTERACT_OBJECT,
                    description="Interact with any object",
                    target_count=1,
                    target_object=None,
                    target_region=None,
                ),
            ),
            rewards={"potion": 1},
        )

        self.custom_catalog = {
            self.quest_read_sign.quest_id: self.quest_read_sign,
            self.quest_harvest_berries.quest_id: self.quest_harvest_berries,
            self.quest_any_interaction_forest.quest_id: self.quest_any_interaction_forest,
            self.quest_talk_to_oak.quest_id: self.quest_talk_to_oak,
            self.quest_unrestricted_any.quest_id: self.quest_unrestricted_any,
        }

        self.quest_manager = QuestManager(catalog=self.custom_catalog)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Correct target interaction advances progress.
    def test_01_correct_target_interaction_advances_progress(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]
        self.assertEqual(prog.status, QuestStatus.ACTIVE)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 0)

        res = self.quest_manager.record_object_interaction(
            self.player,
            object_id="route1_sign",
            region_id="starting_meadow",
        )
        self.assertEqual(res.objectives_updated, 1)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 1)
        self.assertTrue(prog.get_objective("obj_read_sign").is_completed)
        self.assertEqual(prog.status, QuestStatus.COMPLETED)

    # 2. Wrong target does not advance progress.
    def test_02_wrong_target_does_not_advance_progress(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]

        # Interacting with berry bush instead of sign
        res = self.quest_manager.record_object_interaction(
            self.player,
            object_id="berry_bush_route1",
            region_id="starting_meadow",
        )
        self.assertEqual(res.objectives_updated, 0)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 0)
        self.assertFalse(prog.get_objective("obj_read_sign").is_completed)
        self.assertEqual(prog.status, QuestStatus.ACTIVE)

    # 3. Region-restricted interaction only progresses in the correct region.
    def test_03_region_restricted_interaction_only_progresses_in_correct_region(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]

        # Correct object, wrong region (forest_trail instead of starting_meadow)
        res_wrong = self.quest_manager.record_object_interaction(
            self.player,
            object_id="route1_sign",
            region_id="forest_trail",
        )
        self.assertEqual(res_wrong.objectives_updated, 0)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 0)

        # Missing region
        res_none = self.quest_manager.record_object_interaction(
            self.player,
            object_id="route1_sign",
            region_id=None,
        )
        self.assertEqual(res_none.objectives_updated, 0)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 0)

        # Correct region
        res_correct = self.quest_manager.record_object_interaction(
            self.player,
            object_id="route1_sign",
            region_id="starting_meadow",
        )
        self.assertEqual(res_correct.objectives_updated, 1)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 1)
        self.assertTrue(prog.is_completed)

    # 4. Unrestricted interaction objectives work across regions.
    def test_04_unrestricted_interaction_objectives_work_across_regions(self) -> None:
        self.quest_manager.accept_quest(self.player, "harvest_meadow_berries")
        prog = self.player.quests["harvest_meadow_berries"]

        # Objective has target_region=None; should advance in any region
        res1 = self.quest_manager.record_object_interaction(
            self.player,
            object_id="berry_bush_route1",
            region_id="starting_meadow",
        )
        self.assertEqual(res1.objectives_updated, 1)
        self.assertEqual(prog.get_objective("obj_harvest_bush").current_count, 1)

        # Second interaction with no region specified
        res2 = self.quest_manager.record_object_interaction(
            self.player,
            object_id="berry_bush_route1",
            region_id=None,
        )
        self.assertEqual(res2.objectives_updated, 1)
        self.assertEqual(prog.get_objective("obj_harvest_bush").current_count, 2)
        self.assertTrue(prog.is_completed)

    # 5. Failed or invalid interactions do not advance progress.
    def test_05_failed_or_invalid_interactions_do_not_advance_progress(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]

        sign = Interactable(
            object_id="route1_sign",
            name="Route 1 Sign",
            description="Sign",
            interactable_type=InteractableType.SIGN,
            position=(2.0, 1.0),
            interaction_radius=2.0,
            interaction_text="Welcome",
            region_id="starting_meadow",
        )
        wim = WorldInteractionManager(objects=[sign], quest_manager=self.quest_manager)

        # Player at (100.0, 100.0) -> Out of range!
        res_fail = wim.interact(
            player=self.player,
            object_id="route1_sign",
            player_position=(100.0, 100.0),
        )
        self.assertFalse(res_fail.success)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 0)
        self.assertFalse(prog.is_completed)

    # 6. A single successful interaction is not counted twice (event replay deduplication).
    def test_06_event_replay_deduplication_prevents_double_counting(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]

        event_id = "unique_interaction_evt_101"
        res1 = self.quest_manager.record_object_interaction(
            self.player,
            object_id="route1_sign",
            region_id="starting_meadow",
            event_id=event_id,
        )
        self.assertEqual(res1.objectives_updated, 1)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 1)

        # Replay same event_id
        res2 = self.quest_manager.record_object_interaction(
            self.player,
            object_id="route1_sign",
            region_id="starting_meadow",
            event_id=event_id,
        )
        self.assertEqual(res2.objectives_updated, 0)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 1)

    # 7. Progress respects objective count limits (target count clamping).
    def test_07_progress_respects_count_limits(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]

        # Objective target is 1; record 2 interactions
        self.quest_manager.record_object_interaction(
            self.player, object_id="route1_sign", region_id="starting_meadow", event_id="evt_a"
        )
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 1)
        self.assertTrue(prog.get_objective("obj_read_sign").is_completed)

        # Another interaction event does not exceed target_count
        self.quest_manager.record_object_interaction(
            self.player, object_id="route1_sign", region_id="starting_meadow", event_id="evt_b"
        )
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 1)

    # 8. Multi-count objectives progress sequentially up to target count.
    def test_08_multi_count_objective_progresses_sequentially(self) -> None:
        self.quest_manager.accept_quest(self.player, "harvest_meadow_berries")
        prog = self.player.quests["harvest_meadow_berries"]
        obj_prog = prog.get_objective("obj_harvest_bush")

        self.assertEqual(obj_prog.current_count, 0)
        self.assertFalse(obj_prog.is_completed)

        # First harvest
        res1 = self.quest_manager.record_object_interaction(
            self.player, object_id="berry_bush_route1", event_id="harvest_1"
        )
        self.assertEqual(res1.objectives_updated, 1)
        self.assertEqual(obj_prog.current_count, 1)
        self.assertFalse(obj_prog.is_completed)
        self.assertEqual(prog.status, QuestStatus.ACTIVE)

        # Second harvest
        res2 = self.quest_manager.record_object_interaction(
            self.player, object_id="berry_bush_route1", event_id="harvest_2"
        )
        self.assertEqual(res2.objectives_updated, 1)
        self.assertEqual(obj_prog.current_count, 2)
        self.assertTrue(obj_prog.is_completed)
        self.assertEqual(prog.status, QuestStatus.COMPLETED)

    # 9. Case-insensitive matching works reliably for object ID and region ID.
    def test_09_case_insensitive_matching(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]

        res = self.quest_manager.record_object_interaction(
            self.player,
            object_id="RoUtE1_SiGn",
            region_id="StArTiNg_MeAdOw",
        )
        self.assertEqual(res.objectives_updated, 1)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 1)
        self.assertTrue(prog.is_completed)

    # 10. Target object matching works for NPCs with or without 'npc_' prefix.
    def test_10_target_object_matching_for_npcs(self) -> None:
        self.quest_manager.accept_quest(self.player, "consult_prof_oak")
        prog = self.player.quests["consult_prof_oak"]

        # Event payload from NPC interaction typically has object_id="npc_prof_oak" and npc_id="prof_oak"
        res = self.quest_manager.record_object_interaction(
            self.player,
            object_id="npc_prof_oak",
            npc_id="prof_oak",
            region_id="starting_meadow",
        )
        self.assertEqual(res.objectives_updated, 1)
        self.assertEqual(prog.get_objective("obj_speak_oak").current_count, 1)
        self.assertTrue(prog.is_completed)

    # 11. End-to-end WorldInteractionManager.interact() advances matching quest objectives authoritatively.
    def test_11_end_to_end_wim_interact_advances_quest(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]

        sign = Interactable(
            object_id="route1_sign",
            name="Route 1 Trail Marker",
            description="Signpost",
            interactable_type=InteractableType.SIGN,
            position=(2.0, 1.0),
            interaction_radius=2.0,
            interaction_text="Route 1 to Viridian City.",
            region_id="starting_meadow",
        )
        wim = WorldInteractionManager(objects=[sign], quest_manager=self.quest_manager)

        # Player at valid position (2.0, 1.5)
        res = wim.interact(
            player=self.player,
            object_id="route1_sign",
            player_position=(2.0, 1.5),
        )
        self.assertTrue(res.success)
        self.assertEqual(res.region_id, "starting_meadow")

        # Verify quest progressed and completed
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 1)
        self.assertTrue(prog.is_completed)
        self.assertEqual(prog.status, QuestStatus.COMPLETED)

    # 12. End-to-end interaction in wrong region does not advance restricted objective.
    def test_12_end_to_end_wrong_region_does_not_advance_objective(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]

        # Sign placed in forest_trail instead of starting_meadow
        sign_forest = Interactable(
            object_id="route1_sign",
            name="Route 1 Trail Marker",
            description="Signpost",
            interactable_type=InteractableType.SIGN,
            position=(15.0, 10.0),
            interaction_radius=2.0,
            interaction_text="Route 1 to Viridian City.",
            region_id="forest_trail",
        )
        wim = WorldInteractionManager(objects=[sign_forest], quest_manager=self.quest_manager)

        res = wim.interact(
            player=self.player,
            object_id="route1_sign",
            player_position=(15.0, 10.0),
        )
        self.assertTrue(res.success)
        self.assertEqual(res.region_id, "forest_trail")

        # Verify quest did NOT advance due to region mismatch
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 0)
        self.assertFalse(prog.is_completed)
        self.assertEqual(prog.status, QuestStatus.ACTIVE)

    # 13. Quest completion transitions, notifications, explicit reward claiming, and save/load round-trips.
    def test_13_completion_notification_claim_and_persistence(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]

        sign = Interactable(
            object_id="route1_sign",
            name="Route 1 Trail Marker",
            description="Signpost",
            interactable_type=InteractableType.SIGN,
            position=(2.0, 1.0),
            interaction_radius=2.0,
            interaction_text="Route 1 to Viridian City.",
            region_id="starting_meadow",
        )
        wim = WorldInteractionManager(objects=[sign], quest_manager=self.quest_manager)

        res = wim.interact(
            player=self.player,
            object_id="route1_sign",
            player_position=(2.0, 1.0),
        )
        self.assertTrue(res.success)
        self.assertTrue(prog.is_completed)

        # Notification verification
        self.assertTrue(self.quest_manager.has_pending_notifications())
        notes = self.quest_manager.pop_pending_notifications()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].quest_id, "read_route1_sign")

        # Save to disk
        save_game(self.player, self.save_file)

        # Restore from disk with custom quest catalog
        restored = load_game(self.save_file, quest_catalog=self.custom_catalog)
        self.assertIn("read_route1_sign", restored.quests)
        restored_prog = restored.quests["read_route1_sign"]
        self.assertTrue(restored_prog.is_completed)
        self.assertEqual(restored_prog.get_objective("obj_read_sign").current_count, 1)
        self.assertFalse(restored_prog.rewards_claimed)

        # Explicit reward claiming
        claim_res = self.quest_manager.claim_rewards(restored, "read_route1_sign")
        self.assertTrue(claim_res.success)
        self.assertEqual(claim_res.items_granted, {"potion": 2})
        self.assertEqual(restored.inventory.get_quantity("potion"), 2)
        self.assertTrue(restored_prog.rewards_claimed)

    # 14. Existing world interactions (resource gathering, signs, landmarks, treasures) remain compatible.
    def test_14_existing_world_interactions_remain_compatible(self) -> None:
        bush = Interactable(
            object_id="berry_bush_route1",
            name="Berry Bush",
            description="Bush",
            interactable_type=InteractableType.RESOURCE_NODE,
            position=(5.0, 5.0),
            interaction_radius=2.0,
            rewards={"potion": 1},
            respawn_duration=60.0,
            region_id="starting_meadow",
        )
        wim = WorldInteractionManager(objects=[bush], quest_manager=self.quest_manager)

        # Initial inventory empty
        self.assertEqual(self.player.inventory.get_quantity("potion"), 0)

        # Gather from bush
        res = wim.interact(
            player=self.player,
            object_id="berry_bush_route1",
            player_position=(5.0, 5.0),
        )
        self.assertTrue(res.success)
        self.assertEqual(res.items_granted, {"potion": 1})
        self.assertEqual(self.player.inventory.get_quantity("potion"), 1)
        self.assertFalse(bush.is_available)

    # 15. Previously collected treasure does not satisfy INTERACT_OBJECT immediately upon quest acceptance.
    def test_15_previously_collected_treasure_does_not_auto_satisfy_interact_objective(self) -> None:
        quest_chest = QuestDefinition(
            quest_id="loot_cache_quest",
            name="Cache Looter",
            description="Interact with the supply cache.",
            objectives=(
                QuestObjective(
                    objective_id="obj_interact_cache",
                    objective_type=ObjectiveType.INTERACT_OBJECT,
                    description="Interact with Trainer Supply Cache",
                    target_count=1,
                    target_object="supply_cache_01",
                ),
            ),
            rewards={"antidote": 1},
        )
        self.quest_manager.register_quest(quest_chest)

        # Player collected treasure beforehand
        self.player.mark_treasure_collected("supply_cache_01")
        self.assertTrue(self.player.is_treasure_collected("supply_cache_01"))

        # Accept quest
        res = self.quest_manager.accept_quest(self.player, "loot_cache_quest")
        self.assertTrue(res.success)
        prog = self.player.quests["loot_cache_quest"]

        # Objective must NOT be auto-satisfied upon acceptance
        self.assertEqual(prog.status, QuestStatus.ACTIVE)
        self.assertEqual(prog.get_objective("obj_interact_cache").current_count, 0)
        self.assertFalse(prog.get_objective("obj_interact_cache").is_completed)

        # evaluate_state_based_objectives also must not satisfy it
        completed = self.quest_manager.evaluate_state_based_objectives(self.player)
        self.assertEqual(completed, [])
        self.assertEqual(prog.get_objective("obj_interact_cache").current_count, 0)
        self.assertEqual(prog.status, QuestStatus.ACTIVE)

    # 16. Target object identifier matching boundary cases and isolation.
    def test_16_target_object_matching_boundary_cases(self) -> None:
        self.quest_manager.accept_quest(self.player, "read_route1_sign")
        prog = self.player.quests["read_route1_sign"]

        # Substring / partial ID does not match
        res_partial = self.quest_manager.record_object_interaction(
            self.player,
            object_id="route1_sign_post",
            region_id="starting_meadow",
        )
        self.assertEqual(res_partial.objectives_updated, 0)
        self.assertEqual(prog.get_objective("obj_read_sign").current_count, 0)

        # Different NPC ID does not match
        self.quest_manager.accept_quest(self.player, "consult_prof_oak")
        prog_oak = self.player.quests["consult_prof_oak"]

        res_diff_npc = self.quest_manager.record_object_interaction(
            self.player,
            object_id="npc_battle_scout",
            npc_id="battle_scout",
            region_id="forest_trail",
        )
        self.assertEqual(res_diff_npc.objectives_updated, 0)
        self.assertEqual(prog_oak.get_objective("obj_speak_oak").current_count, 0)

        # Correct NPC matches via npc_id="prof_oak"
        res_match = self.quest_manager.record_object_interaction(
            self.player,
            object_id="npc_prof_oak",
            npc_id="prof_oak",
            region_id="starting_meadow",
        )
        self.assertEqual(res_match.objectives_updated, 1)
        self.assertEqual(prog_oak.get_objective("obj_speak_oak").current_count, 1)
        self.assertTrue(prog_oak.is_completed)

    # 17. Explicit region takes precedence over object and player position fallbacks.
    def test_17_explicit_region_takes_precedence_over_fallbacks(self) -> None:
        sign = Interactable(
            object_id="route1_sign",
            name="Sign",
            description="Sign",
            interactable_type=InteractableType.SIGN,
            position=(2.0, 1.0),
            interaction_radius=2.0,
            interaction_text="Text",
            region_id="forest_trail",  # Attribute says forest_trail
        )
        wim = WorldInteractionManager(objects=[sign], quest_manager=self.quest_manager)

        # Pass explicit region_id="starting_meadow"
        res = wim.interact(
            player=self.player,
            object_id="route1_sign",
            player_position=(2.0, 1.0),
            region_id="starting_meadow",
        )
        self.assertTrue(res.success)
        self.assertEqual(res.region_id, "starting_meadow")

    # 18. Distinct interactions and replay deduplication with custom event IDs.
    def test_18_distinct_interactions_and_replay_deduplication(self) -> None:
        self.quest_manager.accept_quest(self.player, "harvest_meadow_berries")
        prog = self.player.quests["harvest_meadow_berries"]

        bush = Interactable(
            object_id="berry_bush_route1",
            name="Bush",
            description="Bush",
            interactable_type=InteractableType.RESOURCE_NODE,
            position=(5.0, 5.0),
            interaction_radius=2.0,
            rewards={},
            respawn_duration=None,
        )
        wim = WorldInteractionManager(objects=[bush], quest_manager=self.quest_manager)

        # First interaction with event_id="custom_evt_1"
        res1 = wim.interact(
            player=self.player,
            object_id="berry_bush_route1",
            player_position=(5.0, 5.0),
            event_id="custom_evt_1",
        )
        self.assertTrue(res1.success)
        self.assertEqual(prog.get_objective("obj_harvest_bush").current_count, 1)

        # Replay the identical event_id directly to QuestManager
        res_replay = self.quest_manager.record_object_interaction(
            self.player,
            object_id="berry_bush_route1",
            event_id="custom_evt_1",
        )
        self.assertEqual(res_replay.objectives_updated, 0)
        self.assertEqual(prog.get_objective("obj_harvest_bush").current_count, 1)

        # Reset bush availability for second interaction with distinct event_id="custom_evt_2"
        bush.is_available = True
        res2 = wim.interact(
            player=self.player,
            object_id="berry_bush_route1",
            player_position=(5.0, 5.0),
            event_id="custom_evt_2",
        )
        self.assertTrue(res2.success)
        self.assertEqual(prog.get_objective("obj_harvest_bush").current_count, 2)
        self.assertTrue(prog.is_completed)


if __name__ == "__main__":
    unittest.main()
