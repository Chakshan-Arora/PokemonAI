"""
Comprehensive test suite for Phase B1: Quest Journal and Progress Display.

Verifies:
- QuestJournal presentation logic (empty states, active, partial, completed).
- Progress bar generation and count formatting (e.g. '3/5', 60.0%).
- Visual distinction between completed and incomplete objectives and quests.
- Overall quest progress calculation and display.
- Unclaimed reward indicator and reward claiming mechanism.
- Protection against premature reward grants: opening or rendering never grants rewards or mutates state.
- Filtering by quest status (All, Active, Completed).
- Pagination and detailed quest dossier inspection.
- End-to-end integration with AdventureGame menu navigation (options '6' -> '3', and shortcut 'j').
"""
import os
import tempfile
import unittest

from game import AdventureGame
from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.quest import (
    QuestStatus,
    QuestDefinition,
    QuestObjective,
    ObjectiveType,
    ObjectiveProgress,
    QuestProgress,
)
from src.models.quest_manager import QuestManager
from src.models.quest_journal import (
    QuestJournal,
    QuestEntryView,
    ObjectiveEntryView,
    make_progress_bar,
)
from src.data.species import CHARMANDER, PIKACHU
from src.data.attacks import TACKLE
from src.data.quests import FIRST_ENCOUNTER, STOCKING_SUPPLIES, SPECIES_RESEARCH


class TestQuestJournal(unittest.TestCase):
    def setUp(self) -> None:
        self.player = Player(name="Ash")
        self.quest_mgr = QuestManager()
        self.journal = QuestJournal(quest_manager=self.quest_mgr)
        self.personality = Personality(50, 50, 50, 50, 50, 50)

    # --- 1. Progress Bar & Utility Formatting ---

    def test_01_make_progress_bar(self) -> None:
        """make_progress_bar correctly renders pure ASCII bars of clamped widths."""
        self.assertEqual(make_progress_bar(0.0, width=10), "[----------]")
        self.assertEqual(make_progress_bar(0.5, width=10), "[=====-----]")
        self.assertEqual(make_progress_bar(1.0, width=10), "[==========]")
        self.assertEqual(make_progress_bar(0.33, width=6), "[==----]")
        # Clamping out-of-bounds inputs
        self.assertEqual(make_progress_bar(-0.5, width=5), "[-----]")
        self.assertEqual(make_progress_bar(1.5, width=5), "[=====]")

    # --- 2. Empty States ---

    def test_02_empty_state_display(self) -> None:
        """Empty journal returns sensible empty state messages without exceptions."""
        entries = self.journal.get_tracked_entries(self.player)
        self.assertEqual(len(entries), 0)

        empty_lines = self.journal.format_empty_state()
        self.assertTrue(any("empty" in line.lower() for line in empty_lines))

        # Filter empty states
        active_empty = self.journal.format_empty_state("active")
        self.assertTrue(any("no active quests" in line.lower() for line in active_empty))

        completed_empty = self.journal.format_empty_state("completed")
        self.assertTrue(any("no completed quests" in line.lower() for line in completed_empty))

        # format_quest_list with empty entries returns empty state lines
        lines, cur_page, total_pages = self.journal.format_quest_list([])
        self.assertEqual(cur_page, 1)
        self.assertEqual(total_pages, 1)
        self.assertTrue(any("empty" in l.lower() for l in lines))

    # --- 3. Active, Partial, and Completed Quest Presentation ---

    def test_03_active_and_partial_quest_presentation(self) -> None:
        """Active quest with partial objective progress displays counts, progress bars, and tags."""
        # Accept First Encounter quest (capture 1 wild Pokemon)
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        entries = self.journal.get_tracked_entries(self.player)
        self.assertEqual(len(entries), 1)

        entry = entries[0]
        self.assertEqual(entry.quest_id, "first_encounter")
        self.assertEqual(entry.name, "First Encounter")
        self.assertEqual(entry.status, QuestStatus.ACTIVE)
        self.assertFalse(entry.is_completed)
        self.assertFalse(entry.can_claim_rewards)
        self.assertEqual(entry.marker, "[*]")
        self.assertEqual(entry.progress_ratio, 0.0)
        self.assertEqual(entry.progress_percentage, 0.0)

        # Inspect objective view
        self.assertEqual(len(entry.objectives), 1)
        obj_view = entry.objectives[0]
        self.assertEqual(obj_view.objective_id, "capture_first_pokemon")
        self.assertEqual(obj_view.formatted_counts, "0/1")
        self.assertEqual(obj_view.remaining_count, 1)
        self.assertEqual(obj_view.marker, "[ ]")
        self.assertEqual(obj_view.status_tag, "[IN PROGRESS]")
        self.assertFalse(obj_view.is_completed)

        # Multi-objective quest with partial completion
        custom_quest = QuestDefinition(
            quest_id="field_study",
            name="Field Study",
            description="Examine wild life.",
            objectives=(
                QuestObjective("catch_mon", ObjectiveType.CAPTURE_ANY, "Catch 4 Pokemon", target_count=4),
                QuestObjective("defeat_mon", ObjectiveType.DEFEAT_ANY, "Defeat 2 Pokemon", target_count=2),
            ),
            prerequisites=(),
            rewards={"potion": 1},
        )
        mgr = QuestManager(catalog={"field_study": custom_quest})
        mgr.accept_quest(self.player, "field_study")
        mgr.advance_objective(self.player, "field_study", "catch_mon", 2)
        mgr.advance_objective(self.player, "field_study", "defeat_mon", 2)  # defeat_mon is complete, catch_mon is 2/4

        journal_custom = QuestJournal(quest_manager=mgr, catalog={"field_study": custom_quest})
        q_entry = journal_custom.get_entry(self.player, "field_study")
        self.assertIsNotNone(q_entry)
        self.assertFalse(q_entry.is_completed)
        self.assertEqual(q_entry.completed_objectives_count, 1)
        self.assertEqual(q_entry.total_objectives_count, 2)
        self.assertAlmostEqual(q_entry.progress_ratio, 4.0 / 6.0)

        obj_catch = next(o for o in q_entry.objectives if o.objective_id == "catch_mon")
        self.assertEqual(obj_catch.formatted_counts, "2/4")
        self.assertEqual(obj_catch.marker, "[ ]")
        self.assertFalse(obj_catch.is_completed)

        obj_defeat = next(o for o in q_entry.objectives if o.objective_id == "defeat_mon")
        self.assertEqual(obj_defeat.formatted_counts, "2/2")
        self.assertEqual(obj_defeat.marker, "[X]")
        self.assertTrue(obj_defeat.is_completed)

    def test_04_completed_quest_reward_unclaimed_presentation(self) -> None:
        """Completed quest with unclaimed rewards clearly flags reward readiness."""
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        self.quest_mgr.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        entry = self.journal.get_entry(self.player, "first_encounter")
        self.assertIsNotNone(entry)
        self.assertTrue(entry.is_completed)
        self.assertTrue(entry.can_claim_rewards)
        self.assertFalse(entry.rewards_claimed)
        self.assertEqual(entry.marker, "[X]")
        self.assertIn("READY TO CLAIM", entry.status_label)
        self.assertEqual(entry.progress_ratio, 1.0)
        self.assertEqual(entry.progress_percentage, 100.0)

        # Render quest list
        lines, _, _ = self.journal.format_quest_list([entry])
        rendered = "\n".join(lines)
        self.assertIn("[READY TO CLAIM!]", rendered)
        self.assertIn("Reward Available", rendered)
        self.assertIn("[X]", rendered)

    # --- 4. Read-Only Safety Verification ---

    def test_05_rendering_journal_never_grants_rewards_or_mutates_state(self) -> None:
        """Inspecting or rendering journal views is strictly read-only and never grants items."""
        # Complete first_encounter
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        self.quest_mgr.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        initial_potions = self.player.inventory.get_quantity("potion")
        self.assertFalse(self.player.quests["first_encounter"].rewards_claimed)

        # Call all journal rendering methods multiple times
        for _ in range(5):
            self.journal.get_tracked_entries(self.player)
            self.journal.format_summary_header(self.player)
            e = self.journal.get_entry(self.player, "first_encounter")
            self.journal.format_quest_list([e])
            self.journal.format_quest_dossier(e)

        # State must remain 100% identical and unclaimed
        self.assertEqual(self.player.inventory.get_quantity("potion"), initial_potions)
        self.assertFalse(self.player.quests["first_encounter"].rewards_claimed)
        self.assertTrue(self.player.quests["first_encounter"].can_claim_rewards)

    # --- 5. Filtering and Pagination ---

    def test_06_journal_status_filtering(self) -> None:
        """Filtering by ACTIVE or COMPLETED separates quests cleanly."""
        # Setup 1 active quest and 1 completed quest
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        self.quest_mgr.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        self.quest_mgr.accept_quest(self.player, "stocking_supplies")  # Player starts with 0 potions, so active

        # All entries
        all_entries = self.journal.get_tracked_entries(self.player)
        self.assertEqual(len(all_entries), 2)

        # Filter active
        active_entries = self.journal.get_tracked_entries(self.player, filter_status="active")
        self.assertEqual(len(active_entries), 1)
        self.assertEqual(active_entries[0].quest_id, "stocking_supplies")

        # Filter completed
        completed_entries = self.journal.get_tracked_entries(self.player, filter_status="completed")
        self.assertEqual(len(completed_entries), 1)
        self.assertEqual(completed_entries[0].quest_id, "first_encounter")

    def test_07_pagination_of_quest_list(self) -> None:
        """Lists with more items than page_size correctly calculate pages and slice entries."""
        mock_entries = [
            QuestEntryView(
                quest_id=f"q_{i}",
                name=f"Quest {i}",
                description="Desc",
                status=QuestStatus.ACTIVE,
                is_completed=False,
                rewards_claimed=False,
                can_claim_rewards=False,
                progress_ratio=0.0,
                progress_percentage=0.0,
                progress_bar="[----------]",
                total_objectives_count=1,
                completed_objectives_count=0,
                remaining_objectives_count=1,
                rewards={},
                prerequisites=(),
                objectives=[],
            )
            for i in range(1, 8)
        ]

        # Page size 3 -> 7 items = 3 pages
        p1_lines, p1_cur, p1_tot = self.journal.format_quest_list(mock_entries, page=1, page_size=3)
        self.assertEqual(p1_cur, 1)
        self.assertEqual(p1_tot, 3)
        p1_text = "\n".join(p1_lines)
        self.assertIn("Quest 1", p1_text)
        self.assertIn("Quest 3", p1_text)
        self.assertNotIn("Quest 4", p1_text)

        p2_lines, p2_cur, p2_tot = self.journal.format_quest_list(mock_entries, page=2, page_size=3)
        self.assertEqual(p2_cur, 2)
        p2_text = "\n".join(p2_lines)
        self.assertIn("Quest 4", p2_text)
        self.assertIn("Quest 6", p2_text)
        self.assertNotIn("Quest 1", p2_text)

        p3_lines, p3_cur, p3_tot = self.journal.format_quest_list(mock_entries, page=3, page_size=3)
        self.assertEqual(p3_cur, 3)
        p3_text = "\n".join(p3_lines)
        self.assertIn("Quest 7", p3_text)

    # --- 6. Detailed Quest Dossier Inspection ---

    def test_08_quest_dossier_formatting(self) -> None:
        """Dossier provides complete objective breakdown, prerequisites, and rewards."""
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        entry = self.journal.get_entry(self.player, "first_encounter")

        dossier_lines = self.journal.format_quest_dossier(entry)
        text = "\n".join(dossier_lines)

        self.assertIn("QUEST DOSSIER: First Encounter", text)
        self.assertIn("Quest ID     : first_encounter", text)
        self.assertIn("Capture any 1 wild Pokemon", text)
        self.assertIn("0/1", text)
        self.assertIn("2x Potion", text)
        self.assertIn("Claim Status: Incomplete", text)

    # --- 7. End-to-End Game Navigation & Input Integration ---

    def test_09_adventure_game_journal_shortcut_navigation(self) -> None:
        """Player can open the Quest Journal directly using 'j' from the main menu."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_file = os.path.join(tmp_dir, "test_journal_save.json")
            logs: list[str] = []

            # Flow: New Game ('1', 'Ash', '1') -> Open Journal ('j') -> Return ('0') -> Title ('10', 'y') -> Quit ('3')
            inputs = iter(["1", "Ash", "1", "j", "0", "10", "y", "3"])

            def mock_in(prompt: str = "") -> str:
                return next(inputs)

            def mock_out(*args, **kwargs) -> None:
                logs.append(" ".join(str(a) for a in args))

            game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=save_file)
            game.run()

            # Confirm Quest Journal was opened
            self.assertTrue(any("QUEST JOURNAL - Ash's Adventure Log" in line for line in logs))
            self.assertTrue(any("JOURNAL ACTIONS" in line for line in logs))

    def test_10_adventure_game_journal_from_quest_menu_and_reward_claiming(self) -> None:
        """Opening Journal via '6' -> '3', inspecting a quest, and claiming rewards."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_file = os.path.join(tmp_dir, "test_journal_claim.json")
            logs: list[str] = []

            # Flow:
            # 1. New Game ('1', 'Ash', '1')
            # 2. Quest menu ('6') -> Accept Stocking Supplies ('1', '4') -> Return to quest menu
            #    (Note: Ash starts with 3 Potions, so Stocking Supplies evaluates to COMPLETED immediately!)
            # 3. Open Detailed Journal ('3')
            # 4. Inspect Quest 1 ('1', '1', '') -> returns to journal
            # 5. Claim Rewards ('3') -> claims rewards through journal!
            # 6. Exit Journal ('0') -> Exit Quest Menu ('0') -> Title ('10', 'y') -> Quit ('3')
            inputs = iter([
                "1", "Ash", "1",
                "6", "1", "4",
                "3",
                "1", "1", "",
                "3",
                "0", "0",
                "10", "y", "3",
            ])

            def mock_in(prompt: str = "") -> str:
                return next(inputs)

            def mock_out(*args, **kwargs) -> None:
                logs.append(" ".join(str(a) for a in args))

            game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=save_file)
            game.run()

            # Verify dossier was inspected
            self.assertTrue(any("QUEST DOSSIER: Stocking Supplies" in line for line in logs))
            # Verify rewards were claimed via journal action 3 (1x super_potion)
            self.assertTrue(any("Claimed rewards for 'Stocking Supplies'" in line for line in logs))
            self.assertEqual(game.player.inventory.get_quantity("super_potion"), 1)


if __name__ == "__main__":
    unittest.main()
