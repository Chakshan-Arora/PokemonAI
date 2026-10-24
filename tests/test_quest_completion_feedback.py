"""
Unit and integration tests for Phase B3: Quest Completion Feedback and Rewards.
Tests quest completion notification detection, announcement deduplication,
multi-quest completions, atomic reward claims, claim feedback, and game loop integration.
"""
import unittest
import tempfile
import os
from typing import Any

from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.inventory import Inventory
from src.models.item import Item, ItemType
from src.models.quest import (
    QuestStatus,
    ObjectiveType,
    QuestEventType,
    QuestObjective,
    QuestDefinition,
    ObjectiveProgress,
    QuestProgress,
)
from src.models.quest_manager import (
    QuestManager,
    QuestNotification,
    QuestRewardResult,
    EventResult,
)
from src.models.quest_journal import (
    QuestJournal,
    QuestEntryView,
    ObjectiveEntryView,
)
from src.models.capture_manager import CaptureManager
from src.models.save_manager import save_game, load_game
from src.data.species import PIKACHU, SQUIRTLE, CHARMANDER
from src.data.quests import QUEST_CATALOG
from src.data.items import ITEM_CATALOG
import game


class TestQuestCompletionFeedback(unittest.TestCase):
    """
    Tests for Phase B3: Quest Completion Feedback and Rewards.
    """

    def setUp(self) -> None:
        self.personality = Personality(50, 50, 50, 50, 50, 50)
        self.starter = Pokemon(species=PIKACHU, personality=self.personality, level=5)
        self.player = Player(name="Ash")
        self.player.add_pokemon(self.starter)
        self.player.add_to_team(self.starter)
        self.player.set_active_pokemon(self.starter)
        self.quest_manager = QuestManager()
        self.journal = QuestJournal(quest_manager=self.quest_manager)

    # --- 1. Completion Feedback on Gameplay Actions ---

    def test_01_completion_notification_on_wild_capture_gameplay(self) -> None:
        """Completing the final objective via gameplay capture generates a completion notification."""
        # Accept 'first_encounter' (requires 1 capture, rewards 2x potion)
        accept_res = self.quest_manager.accept_quest(self.player, "first_encounter")
        self.assertTrue(accept_res.success)
        self.assertFalse(self.quest_manager.has_pending_notifications())

        # Wild capture occurs
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        self.player.add_pokemon(squirtle)
        res = self.quest_manager.record_capture(self.player, "Squirtle", count=1)

        # Quest should be completed
        prog = self.player.quests["first_encounter"]
        self.assertTrue(prog.is_completed)
        self.assertEqual(prog.status, QuestStatus.COMPLETED)
        self.assertIn("first_encounter", res.quests_completed)

        # Notification should be queued in QuestManager and in EventResult
        self.assertTrue(self.quest_manager.has_pending_notifications())
        self.assertEqual(len(res.notifications), 1)

        note = res.notifications[0]
        self.assertEqual(note.quest_id, "first_encounter")
        self.assertEqual(note.quest_name, "First Encounter")
        self.assertEqual(note.status, QuestStatus.COMPLETED)
        self.assertEqual(note.rewards, {"potion": 2})
        self.assertIn("First Encounter", note.message)

        # Pop notification and verify queue is cleared
        popped = self.quest_manager.pop_pending_notifications()
        self.assertEqual(len(popped), 1)
        self.assertEqual(popped[0].quest_id, "first_encounter")
        self.assertFalse(self.quest_manager.has_pending_notifications())

    # --- 2. Deduplication of Completion Notifications ---

    def test_02_no_duplicate_notification_on_repeated_events_or_event_id_replay(self) -> None:
        """Completing a quest notifies once; subsequent events or replays never re-announce."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        event_id = "test_evt_cap_001"

        # First capture completes the quest
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        self.player.add_pokemon(squirtle)
        res1 = self.quest_manager.record_capture(self.player, "Squirtle", count=1, event_id=event_id)
        self.assertEqual(len(res1.quests_completed), 1)
        self.assertEqual(len(res1.notifications), 1)

        # Consume the notification
        self.assertEqual(len(self.quest_manager.pop_pending_notifications()), 1)

        # Replay the exact same event with identical event_id
        res2 = self.quest_manager.record_capture(self.player, "Squirtle", count=1, event_id=event_id)
        self.assertEqual(res2.events_processed, 0)
        self.assertEqual(len(res2.quests_completed), 0)
        self.assertEqual(len(res2.notifications), 0)
        self.assertFalse(self.quest_manager.has_pending_notifications())

        # Capture another wild Pokemon without event_id
        charmander = Pokemon(species=CHARMANDER, personality=self.personality, level=4)
        self.player.add_pokemon(charmander)
        res3 = self.quest_manager.record_capture(self.player, "Charmander", count=1)
        self.assertEqual(len(res3.quests_completed), 0)
        self.assertEqual(len(res3.notifications), 0)
        self.assertFalse(self.quest_manager.has_pending_notifications())

    # --- 3. Multiple Quests Completing from Single Legitimate Action ---

    def test_03_multiple_quests_complete_from_single_legitimate_action(self) -> None:
        """A single gameplay event can fulfill objectives and announce multiple quests safely."""
        q1_def = QuestDefinition(
            quest_id="catch_any_mon",
            name="Catch Any Pokemon",
            description="Catch any wild creature.",
            objectives=(
                QuestObjective(
                    objective_id="catch_any",
                    objective_type=ObjectiveType.CAPTURE_ANY,
                    description="Catch any Pokemon",
                    target_count=1,
                ),
            ),
            rewards={"poke_ball": 2},
        )
        q2_def = QuestDefinition(
            quest_id="catch_squirtle_scout",
            name="Catch Squirtle Scout",
            description="Catch a wild Squirtle.",
            objectives=(
                QuestObjective(
                    objective_id="catch_squirtle",
                    objective_type=ObjectiveType.CAPTURE_SPECIES,
                    description="Catch a Squirtle",
                    target_species="Squirtle",
                    target_count=1,
                ),
            ),
            rewards={"potion": 1},
        )
        custom_catalog = {"catch_any_mon": q1_def, "catch_squirtle_scout": q2_def}
        qm = QuestManager(catalog=custom_catalog)

        qm.accept_quest(self.player, "catch_any_mon")
        qm.accept_quest(self.player, "catch_squirtle_scout")

        # Capture a Squirtle -> advances both quests to completion!
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        self.player.add_pokemon(squirtle)
        res = qm.record_capture(self.player, "Squirtle", count=1)

        self.assertEqual(len(res.quests_completed), 2)
        self.assertIn("catch_any_mon", res.quests_completed)
        self.assertIn("catch_squirtle_scout", res.quests_completed)
        self.assertEqual(len(res.notifications), 2)

        # Verify queued notifications
        notifications = qm.pop_pending_notifications()
        self.assertEqual(len(notifications), 2)
        names = [n.quest_name for n in notifications]
        self.assertIn("Catch Any Pokemon", names)
        self.assertIn("Catch Squirtle Scout", names)

    # --- 4. Successful Reward Claim Reports Actual Rewards ---

    def test_04_successful_reward_claim_reports_actual_rewards(self) -> None:
        """Claiming rewards accurately reports granted items and updates player inventory."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        self.player.add_pokemon(squirtle)
        self.quest_manager.record_capture(self.player, "Squirtle", count=1)

        # Before claim
        self.assertEqual(self.player.inventory.get_quantity("potion"), 0)
        self.assertFalse(self.player.quests["first_encounter"].rewards_claimed)
        self.assertTrue(self.player.quests["first_encounter"].can_claim_rewards)

        # Claim rewards (first_encounter grants 2x potion)
        claim_res = self.quest_manager.claim_rewards(self.player, "first_encounter")
        self.assertTrue(claim_res.success)
        self.assertEqual(claim_res.quest_id, "first_encounter")
        self.assertEqual(claim_res.items_granted, {"potion": 2})
        self.assertIn("successfully claimed", claim_res.message.lower())

        # After claim
        self.assertEqual(self.player.inventory.get_quantity("potion"), 2)
        self.assertTrue(self.player.quests["first_encounter"].rewards_claimed)
        self.assertFalse(self.player.quests["first_encounter"].can_claim_rewards)

    # --- 5. Already-Claimed and Failed Claims Report Accurately ---

    def test_05_already_claimed_reward_reports_failure_without_duplication(self) -> None:
        """Attempting to claim already-claimed rewards fails cleanly with zero item duplication."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        self.player.add_pokemon(squirtle)
        self.quest_manager.record_capture(self.player, "Squirtle", count=1)

        # First claim succeeds
        first_claim = self.quest_manager.claim_rewards(self.player, "first_encounter")
        self.assertTrue(first_claim.success)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 2)

        # Second claim fails
        repeat_claim = self.quest_manager.claim_rewards(self.player, "first_encounter")
        self.assertFalse(repeat_claim.success)
        self.assertEqual(repeat_claim.items_granted, {})
        self.assertIn("already been claimed", repeat_claim.message)
        # Quantity must still be exactly 2
        self.assertEqual(self.player.inventory.get_quantity("potion"), 2)

    def test_06_uncompleted_and_unaccepted_quest_claim_fails_cleanly(self) -> None:
        """Attempting to claim rewards for incomplete or unaccepted quests fails cleanly."""
        # Unaccepted quest
        claim_unaccepted = self.quest_manager.claim_rewards(self.player, "first_encounter")
        self.assertFalse(claim_unaccepted.success)
        self.assertIn("not been accepted", claim_unaccepted.message)

        # Active but incomplete quest
        self.quest_manager.accept_quest(self.player, "first_encounter")
        claim_incomplete = self.quest_manager.claim_rewards(self.player, "first_encounter")
        self.assertFalse(claim_incomplete.success)
        self.assertIn("not completed yet", claim_incomplete.message)

    # --- 6. Inventory Full Atomic Failure Protection ---

    def test_07_inventory_capacity_exceeded_fails_atomically(self) -> None:
        """If inventory cannot hold rewards, claiming fails atomically without mutating inventory or progress."""
        inv = Inventory(capacity=1)
        inv.add_item("poke_ball", 1)  # Fill sole slot with an unrelated item
        player = Player(name="Ash", inventory=inv)
        player.add_pokemon(self.starter)

        self.quest_manager.accept_quest(player, "first_encounter")
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        player.add_pokemon(squirtle)
        self.quest_manager.record_capture(player, "Squirtle", count=1)

        # Attempt to claim rewards (first_encounter grants potion, which requires a 2nd slot!)
        claim_res = self.quest_manager.claim_rewards(player, "first_encounter")
        self.assertFalse(claim_res.success)
        self.assertIn("capacity exceeded", claim_res.message)

        # Verify state was not partially mutated
        self.assertEqual(player.inventory.slots_used, 1)
        self.assertEqual(player.inventory.get_quantity("potion"), 0)
        self.assertFalse(player.quests["first_encounter"].rewards_claimed)

        # Free space in inventory
        player.inventory.remove_item("poke_ball", 1)
        # Retry claim
        second_res = self.quest_manager.claim_rewards(player, "first_encounter")
        self.assertTrue(second_res.success)
        self.assertEqual(player.inventory.get_quantity("potion"), 2)
        self.assertTrue(player.quests["first_encounter"].rewards_claimed)

    # --- 7. No Rewards Granted by Rendering, Opening, or Dismissing ---

    def test_08_rendering_journal_or_inspecting_never_grants_rewards(self) -> None:
        """Viewing journal summaries, lists, or dossiers never mutates inventory or marks rewards claimed."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        self.player.add_pokemon(squirtle)
        self.quest_manager.record_capture(self.player, "Squirtle", count=1)

        prog = self.player.quests["first_encounter"]
        self.assertTrue(prog.is_completed)
        self.assertFalse(prog.rewards_claimed)
        initial_inv = dict(self.player.inventory._items)

        # Multiple journal renders
        _ = self.journal.get_tracked_entries(self.player)
        _ = self.journal.format_summary_header(self.player)
        entries = self.journal.get_tracked_entries(self.player)
        _ = self.journal.format_quest_list(entries)
        entry = self.journal.get_entry(self.player, "first_encounter")
        self.assertIsNotNone(entry)
        _ = self.journal.format_quest_dossier(entry)

        # Verify zero side effects
        self.assertFalse(prog.rewards_claimed)
        self.assertEqual(dict(self.player.inventory._items), initial_inv)

    def test_09_displaying_and_clearing_notifications_does_not_mutate_rewards(self) -> None:
        """Displaying, popping, or clearing notifications does not grant rewards."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        self.player.add_pokemon(squirtle)
        self.quest_manager.record_capture(self.player, "Squirtle", count=1)

        notes = self.quest_manager.pop_pending_notifications()
        self.assertEqual(len(notes), 1)

        # Render notification banner
        banner = notes[0].format_banner()
        self.assertTrue(any("QUEST COMPLETED" in line for line in banner))

        # Verify rewards remain unclaimed
        prog = self.player.quests["first_encounter"]
        self.assertFalse(prog.rewards_claimed)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 0)

    # --- 8. Immediate Completion on Acceptance Enqueues Notification ---

    def test_10_immediate_completion_upon_acceptance_enqueues_notification(self) -> None:
        """Accepting a quest when requirements are pre-met enqueues a completion notification immediately."""
        # Stocking supplies requires 3 potions. Add 3 Potions to inventory.
        self.player.inventory.add_item("potion", 3)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 3)
        self.assertFalse(self.quest_manager.has_pending_notifications())

        res = self.quest_manager.accept_quest(self.player, "stocking_supplies")
        self.assertTrue(res.success)
        self.assertIn("immediately completed", res.message)

        # Verify notification was queued
        self.assertTrue(self.quest_manager.has_pending_notifications())
        notes = self.quest_manager.pop_pending_notifications()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].quest_id, "stocking_supplies")
        self.assertEqual(notes[0].quest_name, "Stocking Supplies")
        self.assertEqual(notes[0].rewards, {"super_potion": 1})

    # --- 9. Save/Load Round-Trip and No Resurrected Notifications ---

    def test_11_save_load_preserves_completed_and_claimed_state_no_resurrected_notifications(self) -> None:
        """Completed and claimed quest states survive save/load; loaded completed quests do not re-notify."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = os.path.join(tmp_dir, "test_b3_save.json")

            # Player completes first_encounter and claims rewards
            self.quest_manager.accept_quest(self.player, "first_encounter")
            squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
            self.player.add_pokemon(squirtle)
            self.quest_manager.record_capture(self.player, "Squirtle", count=1)
            self.quest_manager.claim_rewards(self.player, "first_encounter")

            # Player also accepts stocking_supplies (completed, but unclaimed)
            self.player.inventory.add_item("potion", 3)
            self.quest_manager.accept_quest(self.player, "stocking_supplies")

            # Clear any pending notifications before save
            self.quest_manager.clear_pending_notifications()

            # Save player
            save_game(self.player, save_path)

            # Load into AdventureGame
            game_inst = game.AdventureGame(save_file=save_path)
            loaded = game_inst.load_game()
            self.assertTrue(loaded)

            # Check that display_quest_notifications displays nothing (no resurrected alerts)
            displayed = game_inst._display_quest_notifications()
            self.assertEqual(len(displayed), 0)

            # Check journal views on the loaded player
            entries = game_inst.quest_journal.get_tracked_entries(game_inst.player)
            entry_map = {e.quest_id: e for e in entries}

            self.assertTrue(entry_map["first_encounter"].rewards_claimed)
            self.assertFalse(entry_map["first_encounter"].can_claim_rewards)

            self.assertTrue(entry_map["stocking_supplies"].is_completed)
            self.assertFalse(entry_map["stocking_supplies"].rewards_claimed)
            self.assertTrue(entry_map["stocking_supplies"].can_claim_rewards)

    # --- 10. Claim All Helper ---

    def test_12_claim_all_completed_rewards_helper(self) -> None:
        """claim_all_completed_rewards claims all completed quests with pending rewards."""
        # Set up 2 claimable quests
        self.quest_manager.accept_quest(self.player, "first_encounter")
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        self.player.add_pokemon(squirtle)
        self.quest_manager.record_capture(self.player, "Squirtle", count=1)

        self.player.inventory.add_item("potion", 3)
        self.quest_manager.accept_quest(self.player, "stocking_supplies")

        results = self.quest_manager.claim_all_completed_rewards(self.player)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.success for r in results))

        # Check inventory received rewards:
        # first_encounter grants 2 potions (initial 3 + 2 = 5)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 5)
        # stocking_supplies grants 1 super_potion
        self.assertEqual(self.player.inventory.get_quantity("super_potion"), 1)

        # Repeating returns empty list
        empty_results = self.quest_manager.claim_all_completed_rewards(self.player)
        self.assertEqual(len(empty_results), 0)

    # --- 11. Notification Callback Integration ---

    def test_13_on_quest_completed_callback(self) -> None:
        """Registering on_quest_completed invokes the listener on quest transition."""
        callbacks_received: list[QuestNotification] = []
        self.quest_manager.on_quest_completed = lambda note: callbacks_received.append(note)

        self.quest_manager.accept_quest(self.player, "first_encounter")
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        self.player.add_pokemon(squirtle)
        self.quest_manager.record_capture(self.player, "Squirtle", count=1)

        self.assertEqual(len(callbacks_received), 1)
        self.assertEqual(callbacks_received[0].quest_id, "first_encounter")
        self.assertEqual(callbacks_received[0].quest_name, "First Encounter")

    # --- 12. Journal Formatting Helpers ---

    def test_14_quest_journal_format_claim_result_and_notification(self) -> None:
        """QuestJournal formatting helpers produce readable feedback."""
        note = QuestNotification(
            quest_id="test_q",
            quest_name="Test Quest",
            status=QuestStatus.COMPLETED,
            rewards={"poke_ball": 5},
            message="Test Quest completed!",
        )
        banner = self.journal.format_completion_notification(note)
        self.assertTrue(any("QUEST COMPLETED: 'Test Quest'" in line for line in banner))
        self.assertTrue(any("5x Poke Ball" in line for line in banner))

        success_res = QuestRewardResult(
            success=True,
            quest_id="test_q",
            items_granted={"poke_ball": 5},
            message="Rewards granted",
        )
        success_lines = self.journal.format_claim_result(success_res, "Test Quest")
        self.assertTrue(any("Claimed rewards for 'Test Quest': 5x Poke Ball" in line for line in success_lines))

        fail_res = QuestRewardResult(
            success=False,
            quest_id="test_q",
            items_granted={},
            message="Inventory full",
        )
        fail_lines = self.journal.format_claim_result(fail_res, "Test Quest")
        self.assertTrue(any("Could not claim rewards for 'Test Quest': Inventory full" in line for line in fail_lines))

    # --- 13. End-to-End AdventureGame Integration ---

    def test_15_adventure_game_battle_completion_and_reward_claim_integration(self) -> None:
        """End-to-end integration: gameplay battle capture announces completion and claim menu grants rewards."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = os.path.join(tmp_dir, "test_e2e_b3.json")
            logs: list[str] = []

            # Flow:
            # 1. New Game ('1', 'Ash', '1')
            # 2. Quest Menu ('6') -> Accept First Encounter ('1', '1') -> Back ('0')
            # 3. Explore tall grass ('1') -> Wild encounter -> Throw Poke Ball ('3') -> Capture!
            #    (Notice: This battle capture completes First Encounter and displays [!] QUEST COMPLETED!)
            # 4. Quest Menu ('6') -> Claim Rewards ('2') -> Back ('0')
            # 5. Quit Game ('10', 'y', '3')
            inputs = iter([
                "1", "Ash", "1",
                "6", "1", "1", "0",
                "1",
                "3",
                "6", "2", "0",
                "10", "y", "3",
            ])

            def mock_in(prompt: str = "") -> str:
                return next(inputs)

            def mock_out(*args: Any, **kwargs: Any) -> None:
                logs.append(" ".join(str(a) for a in args))

            g = game.AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=save_path, seed=42)
            g.capture_manager._min_probability = 1.0  # 100% capture rate for determinism
            g.run()

            # 1. Verify capture succeeded
            self.assertTrue(any("Congratulations! You caught the wild" in line for line in logs))
            # 2. Verify completion notification banner was displayed
            self.assertTrue(any("QUEST COMPLETED: 'First Encounter'" in line for line in logs))
            self.assertTrue(any("Rewards available to claim" in line for line in logs))
            # 3. Verify available rewards were announced prior to claiming
            self.assertTrue(any("Available rewards for 'First Encounter': 2x Potion" in line for line in logs))
            # 4. Verify claim succeeded and was reported
            self.assertTrue(any("Claimed rewards for 'First Encounter': 2x potion" in line for line in logs))
            # 5. Verify inventory actually received the 2 potions (initial 3 + 2 = 5)
            self.assertEqual(g.player.inventory.get_quantity("potion"), 5)
            # 6. Verify quest state reflects claimed
            self.assertTrue(g.player.quests["first_encounter"].rewards_claimed)


if __name__ == "__main__":
    unittest.main()
