"""
Comprehensive test suite for Phase C3: Branching Quests & Choices.

Verifies:
1. QuestChoiceOption and QuestChoice model definition and validation.
2. QuestDefinition choice validation, identifier uniqueness, and branch objective integrity.
3. Choice availability lifecycle (prerequisite objective gating, active state requirements).
4. make_choice input validation, error handling, and rejection of invalid states.
5. Prevention of contradictory choices and duplicate submissions.
6. Branch-specific objective progression and isolation of unselected branches.
7. Choice-driven quest completion, notifications, and atomic reward delivery.
8. Option-specific rewards combined with base rewards and explicit claim requirement.
9. Full persistence and save/load round-trip for selected choices and branch objectives.
10. Backward compatibility with legacy save payloads without selected_choices.
11. Representative branching quest 1: Shrine Investigation (peaceful vs combat branches).
12. Representative branching quest 2: Research Specialization (immediate choice: capture vs defeat).
13. Quest journal presentation of chosen paths and active branch objectives.
14. End-to-end NPC dialogue flow with choice presentation and player selection.
"""
import tempfile
import unittest

from game import AdventureGame
from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.quest import (
    QuestStatus,
    ObjectiveType,
    QuestEventType,
    QuestObjective,
    QuestDefinition,
    ObjectiveProgress,
    QuestProgress,
    QuestChoice,
    QuestChoiceOption,
)
from src.models.quest_manager import QuestManager
from src.models.quest_journal import QuestJournal
from src.models.save_manager import serialize_player, deserialize_player, save_game, load_game
from src.models.world_interaction_manager import WorldInteractionManager
from src.data.species import PIKACHU
from src.data.quests import (
    QUEST_CATALOG,
    FIRST_ENCOUNTER,
    SHRINE_INVESTIGATION,
    RESEARCH_SPECIALIZATION,
)
from src.data.npcs import get_npc, NPC_CATALOG


class TestBranchingQuests(unittest.TestCase):
    def setUp(self) -> None:
        self.player = Player(name="Red")
        self.quest_manager = QuestManager()
        self.personality = Personality(50, 50, 50, 50, 50, 50)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.personality, level=5)
        self.player.add_pokemon(self.pikachu)
        self.player.add_to_team(self.pikachu)
        self.player.set_active_pokemon(self.pikachu)

    # --- 1. Model Definition & Validation ---

    def test_01_choice_and_option_definition_validation(self) -> None:
        """Valid and invalid QuestChoiceOption and QuestChoice instantiation."""
        # Valid option
        opt = QuestChoiceOption(
            option_id="opt_a",
            text="Option A",
            description="First branch path",
            objectives=(
                QuestObjective("obj_a", ObjectiveType.CAPTURE_ANY, "Catch 1 Pokemon", target_count=1),
            ),
            rewards={"potion": 2},
        )
        self.assertEqual(opt.option_id, "opt_a")
        self.assertEqual(opt.text, "Option A")
        self.assertEqual(len(opt.objectives), 1)
        self.assertEqual(opt.rewards, {"potion": 2})

        # Invalid option: empty option_id
        with self.assertRaises(ValueError):
            QuestChoiceOption(option_id="", text="Option A")

        # Invalid option: empty text
        with self.assertRaises(ValueError):
            QuestChoiceOption(option_id="opt_a", text="")

        # Invalid option: non-dict rewards
        with self.assertRaises(TypeError):
            QuestChoiceOption(option_id="opt_a", text="Option A", rewards=[1, 2])  # type: ignore

        # Invalid option: duplicate branch objective IDs
        with self.assertRaises(ValueError):
            QuestChoiceOption(
                option_id="opt_a",
                text="Option A",
                objectives=(
                    QuestObjective("dup_id", ObjectiveType.CAPTURE_ANY, "Catch 1", target_count=1),
                    QuestObjective("dup_id", ObjectiveType.DEFEAT_ANY, "Defeat 1", target_count=1),
                ),
            )

        # Valid choice
        opt_b = QuestChoiceOption(option_id="opt_b", text="Option B")
        choice = QuestChoice(
            choice_id="choice_path",
            prompt="Which path do you choose?",
            options=(opt, opt_b),
            prerequisite_objectives=("base_obj",),
        )
        self.assertEqual(choice.choice_id, "choice_path")
        self.assertEqual(len(choice.options), 2)
        self.assertEqual(choice.get_option("opt_a"), opt)
        self.assertEqual(choice.get_option("OPT_B"), opt_b)
        self.assertIsNone(choice.get_option("unknown"))

        # Invalid choice: fewer than 2 options
        with self.assertRaises(ValueError):
            QuestChoice(choice_id="ch_1", prompt="Prompt", options=(opt,))

        # Invalid choice: duplicate option IDs
        opt_a_dup = QuestChoiceOption(option_id="opt_a", text="Duplicate A")
        with self.assertRaises(ValueError):
            QuestChoice(choice_id="ch_1", prompt="Prompt", options=(opt, opt_a_dup))

    def test_02_quest_definition_with_choices_validation(self) -> None:
        """QuestDefinition correctly validates choices, unique IDs, and branch objectives."""
        opt_1 = QuestChoiceOption(
            option_id="opt_1",
            text="Opt 1",
            objectives=(
                QuestObjective("obj_branch_1", ObjectiveType.CAPTURE_ANY, "Catch 1", target_count=1),
            ),
        )
        opt_2 = QuestChoiceOption(
            option_id="opt_2",
            text="Opt 2",
            objectives=(
                QuestObjective("obj_branch_2", ObjectiveType.DEFEAT_ANY, "Defeat 1", target_count=1),
            ),
        )
        choice = QuestChoice(choice_id="ch_main", prompt="Pick one", options=(opt_1, opt_2))

        # Valid quest definition
        q_def = QuestDefinition(
            quest_id="branch_quest",
            name="Branch Quest",
            description="A quest with branches.",
            objectives=(
                QuestObjective("obj_base", ObjectiveType.DISCOVER_REGION, "Visit Meadow", target_count=1),
            ),
            choices=(choice,),
        )
        self.assertTrue(q_def.has_choices())
        self.assertEqual(q_def.get_choice("ch_main"), choice)
        self.assertEqual(len(q_def.get_all_objectives()), 3)

        # Valid quest with NO base objectives but WITH choices
        q_def_no_base = QuestDefinition(
            quest_id="branch_only",
            name="Branch Only",
            description="Branch only.",
            choices=(choice,),
        )
        self.assertEqual(len(q_def_no_base.objectives), 0)
        self.assertEqual(len(q_def_no_base.get_all_objectives()), 2)

        # Invalid quest: neither objectives nor choices
        with self.assertRaises(ValueError):
            QuestDefinition(quest_id="empty_quest", name="Empty", description="Empty")

        # Invalid quest: duplicate objective ID between base and branch
        opt_conflict = QuestChoiceOption(
            option_id="opt_c",
            text="Opt C",
            objectives=(
                QuestObjective("obj_base", ObjectiveType.CAPTURE_ANY, "Conflict", target_count=1),
            ),
        )
        ch_conflict = QuestChoice(choice_id="ch_conf", prompt="P", options=(opt_1, opt_conflict))
        with self.assertRaises(ValueError):
            QuestDefinition(
                quest_id="conflict_quest",
                name="Conflict",
                description="Conflict",
                objectives=(
                    QuestObjective("obj_base", ObjectiveType.DISCOVER_REGION, "Visit", target_count=1),
                ),
                choices=(ch_conflict,),
            )

    # --- 2. Choice Availability Lifecycle ---

    def test_03_choice_availability_lifecycle(self) -> None:
        """Choices are only available when the quest is active and prerequisites are satisfied."""
        opt_a = QuestChoiceOption("branch_a", "Branch A")
        opt_b = QuestChoiceOption("branch_b", "Branch B")
        choice = QuestChoice(
            choice_id="decision_1",
            prompt="Choose your method",
            options=(opt_a, opt_b),
            prerequisite_objectives=("base_step",),
        )
        quest = QuestDefinition(
            quest_id="gated_choice_quest",
            name="Gated Quest",
            description="Gated choice testing.",
            objectives=(
                QuestObjective("base_step", ObjectiveType.DISCOVER_REGION, "Explore", target_count=1),
            ),
            choices=(choice,),
        )
        self.quest_manager.register_quest(quest)

        # 1. Unaccepted quest: choice is NOT available
        self.assertFalse(self.quest_manager.is_choice_available(self.player, "gated_choice_quest", "decision_1"))
        self.assertEqual(self.quest_manager.get_available_choices(self.player, "gated_choice_quest"), [])

        # 2. Accepted quest: base_step not yet complete -> choice is NOT available
        self.quest_manager.accept_quest(self.player, "gated_choice_quest")
        self.assertFalse(self.quest_manager.is_choice_available(self.player, "gated_choice_quest", "decision_1"))
        self.assertEqual(self.quest_manager.get_available_choices(self.player, "gated_choice_quest"), [])

        # 3. Advance base_step to completion -> choice BECOMES available
        self.quest_manager.advance_objective(self.player, "gated_choice_quest", "base_step", 1)
        self.assertTrue(self.quest_manager.is_choice_available(self.player, "gated_choice_quest", "decision_1"))
        avail = self.quest_manager.get_available_choices(self.player, "gated_choice_quest")
        self.assertEqual(len(avail), 1)
        self.assertEqual(avail[0].choice_id, "decision_1")

        # 4. Make choice -> choice is NO LONGER available (already committed)
        res = self.quest_manager.make_choice(self.player, "gated_choice_quest", "decision_1", "branch_a")
        self.assertTrue(res.success)
        self.assertFalse(self.quest_manager.is_choice_available(self.player, "gated_choice_quest", "decision_1"))
        self.assertEqual(self.quest_manager.get_available_choices(self.player, "gated_choice_quest"), [])

    # --- 3. Choice Validation & Error Handling ---

    def test_04_make_choice_validation_and_error_handling(self) -> None:
        """make_choice rejects malformed, unaccepted, locked, or invalid choice arguments cleanly."""
        opt_a = QuestChoiceOption("a", "Path A")
        opt_b = QuestChoiceOption("b", "Path B")
        choice = QuestChoice("path_ch", "Prompt", (opt_a, opt_b))
        q = QuestDefinition("test_val_q", "Validation Quest", "Desc", choices=(choice,))
        self.quest_manager.register_quest(q)

        # Non-player type
        with self.assertRaises(TypeError):
            self.quest_manager.make_choice("NotAPlayer", "test_val_q", "path_ch", "a")  # type: ignore

        # Unknown quest
        res = self.quest_manager.make_choice(self.player, "unknown_q", "path_ch", "a")
        self.assertFalse(res.success)
        self.assertIn("not found", res.message)

        # Unaccepted quest
        res = self.quest_manager.make_choice(self.player, "test_val_q", "path_ch", "a")
        self.assertFalse(res.success)
        self.assertIn("not been accepted", res.message)

        # Accept quest
        self.quest_manager.accept_quest(self.player, "test_val_q")

        # Unknown choice ID
        res = self.quest_manager.make_choice(self.player, "test_val_q", "invalid_choice_id", "a")
        self.assertFalse(res.success)
        self.assertIn("does not exist", res.message)

        # Unknown option ID
        res = self.quest_manager.make_choice(self.player, "test_val_q", "path_ch", "invalid_option_id")
        self.assertFalse(res.success)
        self.assertIn("Option 'invalid_option_id' does not exist", res.message)

    def test_05_rejection_of_contradictory_and_duplicate_choices(self) -> None:
        """Committed choice cannot be overwritten, and duplicate submission fails cleanly."""
        opt_a = QuestChoiceOption("path_a", "Path A")
        opt_b = QuestChoiceOption("path_b", "Path B")
        choice = QuestChoice("ch_branch", "Prompt", (opt_a, opt_b))
        q = QuestDefinition("immutable_choice_q", "Imm Quest", "Desc", choices=(choice,))
        self.quest_manager.register_quest(q)
        self.quest_manager.accept_quest(self.player, "immutable_choice_q")

        # First choice succeeds
        res1 = self.quest_manager.make_choice(self.player, "immutable_choice_q", "ch_branch", "path_a")
        self.assertTrue(res1.success)

        prog = self.player.quests["immutable_choice_q"]
        self.assertEqual(prog.get_selected_option("ch_branch"), "path_a")

        # Idempotent re-submission of exact same choice fails cleanly without state modification
        res2 = self.quest_manager.make_choice(self.player, "immutable_choice_q", "ch_branch", "path_a")
        self.assertFalse(res2.success)
        self.assertIn("already been made", res2.message)
        self.assertEqual(prog.get_selected_option("ch_branch"), "path_a")

        # Contradictory re-submission attempting to switch to Path B is strictly rejected
        res3 = self.quest_manager.make_choice(self.player, "immutable_choice_q", "ch_branch", "path_b")
        self.assertFalse(res3.success)
        self.assertIn("Cannot change previously committed choice", res3.message)
        self.assertEqual(prog.get_selected_option("ch_branch"), "path_a")

    # --- 4. Branch Objectives & Isolation ---

    def test_06_branch_objective_activation_and_unselected_branch_isolation(self) -> None:
        """Selected branch activates its objectives; unselected branch objectives never advance."""
        opt_peace = QuestChoiceOption(
            option_id="peace",
            text="Peaceful Path",
            objectives=(
                QuestObjective("obj_peace_gather", ObjectiveType.COLLECT_ITEM, "Gather 2 Potions", target_count=2, target_item="potion"),
            ),
            rewards={"potion": 2},
        )
        opt_combat = QuestChoiceOption(
            option_id="combat",
            text="Combat Path",
            objectives=(
                QuestObjective("obj_combat_defeat", ObjectiveType.DEFEAT_ANY, "Defeat 3 Pokemon", target_count=3),
            ),
            rewards={"super_potion": 2},
        )
        choice = QuestChoice("playstyle", "Select playstyle", (opt_peace, opt_combat))
        quest = QuestDefinition(
            quest_id="playstyle_quest",
            name="Playstyle Quest",
            description="Choose playstyle.",
            objectives=(
                QuestObjective("obj_shared_start", ObjectiveType.DISCOVER_REGION, "Visit meadow", target_count=1),
            ),
            choices=(choice,),
            rewards={"super_potion": 1},
        )
        self.quest_manager.register_quest(quest)
        self.quest_manager.accept_quest(self.player, "playstyle_quest")

        prog = self.player.quests["playstyle_quest"]
        # Only shared base objective is initially active
        self.assertIn("obj_shared_start", prog.objective_progress)
        self.assertNotIn("obj_peace_gather", prog.objective_progress)
        self.assertNotIn("obj_combat_defeat", prog.objective_progress)

        # Player commits to 'peace'
        self.quest_manager.make_choice(self.player, "playstyle_quest", "playstyle", "peace")

        # Now obj_peace_gather is active; obj_combat_defeat is NOT active
        self.assertIn("obj_peace_gather", prog.objective_progress)
        self.assertNotIn("obj_combat_defeat", prog.objective_progress)

        # Fire combat event (matching the unselected branch)
        self.quest_manager.record_event(
            self.player,
            QuestEventType.POKEMON_DEFEATED,
            {"species": "Pikachu", "count": 1},
        )
        # Verify unselected branch did not get added or progressed
        self.assertNotIn("obj_combat_defeat", prog.objective_progress)
        self.assertEqual(prog.get_objective("obj_peace_gather").current_count, 0)
        self.assertFalse(prog.is_completed)

        # Fire item collected event (matching the selected branch)
        self.player.inventory.add_item("potion", 2)
        self.quest_manager.record_event(
            self.player,
            QuestEventType.ITEM_COLLECTED,
            {"item_id": "potion", "quantity": 2},
        )
        self.assertEqual(prog.get_objective("obj_peace_gather").current_count, 2)
        self.assertTrue(prog.get_objective("obj_peace_gather").is_completed)

        # Advance shared objective
        self.quest_manager.advance_objective(self.player, "playstyle_quest", "obj_shared_start", 1)

        # Quest should now be complete!
        self.assertTrue(prog.is_completed)
        self.assertEqual(prog.status, QuestStatus.COMPLETED)

        # Effective rewards include base reward (super_potion: 1) + peace reward (potion: 2)
        effective_rewards = self.quest_manager.get_effective_rewards(self.player, "playstyle_quest")
        self.assertEqual(effective_rewards, {"super_potion": 1, "potion": 2})

    # --- 5. Atomic Reward Claiming ---

    def test_07_choice_rewards_atomic_claim_and_duplicate_protection(self) -> None:
        """Option-specific rewards merge with base rewards and require explicit claiming."""
        opt_a = QuestChoiceOption("opt_a", "Path A", rewards={"potion": 1, "antidote": 2})
        opt_b = QuestChoiceOption("opt_b", "Path B", rewards={"super_potion": 1})
        choice = QuestChoice("ch_rew", "Choose Reward Path", (opt_a, opt_b))
        quest = QuestDefinition(
            quest_id="rew_quest",
            name="Reward Quest",
            description="Test option rewards.",
            objectives=(
                QuestObjective("obj_step", ObjectiveType.DISCOVER_REGION, "Step", target_count=1),
            ),
            choices=(choice,),
            rewards={"super_potion": 2},
        )
        self.quest_manager.register_quest(quest)
        self.quest_manager.accept_quest(self.player, "rew_quest")

        self.quest_manager.make_choice(self.player, "rew_quest", "ch_rew", "opt_a")
        self.quest_manager.advance_objective(self.player, "rew_quest", "obj_step", 1)

        prog = self.player.quests["rew_quest"]
        self.assertTrue(prog.is_completed)
        self.assertTrue(prog.can_claim_rewards)
        self.assertFalse(prog.rewards_claimed)

        # Verify items were NOT yet granted before claiming
        self.assertEqual(self.player.inventory.get_quantity("super_potion"), 0)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 0)
        self.assertEqual(self.player.inventory.get_quantity("antidote"), 0)

        # Claim rewards explicitly
        res = self.quest_manager.claim_rewards(self.player, "rew_quest")
        self.assertTrue(res.success)
        self.assertTrue(prog.rewards_claimed)
        self.assertFalse(prog.can_claim_rewards)

        # Verify all items granted atomically
        self.assertEqual(self.player.inventory.get_quantity("super_potion"), 2)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 1)
        self.assertEqual(self.player.inventory.get_quantity("antidote"), 2)

        # Duplicate claim attempt is rejected
        dup_res = self.quest_manager.claim_rewards(self.player, "rew_quest")
        self.assertFalse(dup_res.success)
        self.assertIn("already been claimed", dup_res.message)
        # Inventory counts remain unchanged
        self.assertEqual(self.player.inventory.get_quantity("super_potion"), 2)

    # --- 6. Save/Load Round-Trip & Persistence ---

    def test_08_save_load_round_trip_preserves_selected_choices_and_branch_progress(self) -> None:
        """Selected choices and active branch objective progress survive serialization and deserialization."""
        # Setup branching quest
        opt_research = QuestChoiceOption(
            option_id="research",
            text="Research Branch",
            objectives=(
                QuestObjective("obj_res_mon", ObjectiveType.CAPTURE_ANY, "Catch 3 Mon", target_count=3),
            ),
            rewards={"super_potion": 1},
        )
        opt_battle = QuestChoiceOption(
            option_id="battle",
            text="Battle Branch",
            objectives=(
                QuestObjective("obj_bat_mon", ObjectiveType.DEFEAT_ANY, "Defeat 3 Mon", target_count=3),
            ),
            rewards={"potion": 3},
        )
        choice = QuestChoice("branch_choice", "Choose field", (opt_research, opt_battle))
        quest = QuestDefinition(
            quest_id="branch_save_quest",
            name="Branch Save Quest",
            description="Testing save/load.",
            objectives=(
                QuestObjective("obj_base_init", ObjectiveType.DISCOVER_REGION, "Init", target_count=1),
            ),
            choices=(choice,),
            rewards={"pokeball": 5},
        )
        self.quest_manager.register_quest(quest)
        self.quest_manager.accept_quest(self.player, "branch_save_quest")

        # Make choice 'research'
        self.quest_manager.make_choice(self.player, "branch_save_quest", "branch_choice", "research")
        # Partial progress on branch objective
        self.quest_manager.advance_objective(self.player, "branch_save_quest", "obj_res_mon", 2)

        # Serialize
        serialized = serialize_player(self.player)
        self.assertIn("quests", serialized)
        self.assertIn("branch_save_quest", serialized["quests"])
        q_save = serialized["quests"]["branch_save_quest"]
        self.assertEqual(q_save["selected_choices"], {"branch_choice": "research"})
        self.assertIn("obj_res_mon", q_save["objective_progress"])
        self.assertNotIn("obj_bat_mon", q_save["objective_progress"])

        # Deserialize into a fresh player instance
        restored = deserialize_player(serialized, quest_catalog=self.quest_manager.catalog)
        self.assertIn("branch_save_quest", restored.quests)
        r_prog = restored.quests["branch_save_quest"]
        self.assertEqual(r_prog.selected_choices, {"branch_choice": "research"})
        self.assertIn("obj_res_mon", r_prog.objective_progress)
        self.assertNotIn("obj_bat_mon", r_prog.objective_progress)
        self.assertEqual(r_prog.get_objective("obj_res_mon").current_count, 2)
        self.assertEqual(r_prog.get_objective("obj_res_mon").target_count, 3)

        # Round-trip via temp file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            save_path = tf.name

        try:
            save_game(self.player, save_path)
            loaded = load_game(save_path, quest_catalog=self.quest_manager.catalog)
            l_prog = loaded.quests["branch_save_quest"]
            self.assertEqual(l_prog.selected_choices, {"branch_choice": "research"})
            self.assertEqual(l_prog.get_objective("obj_res_mon").current_count, 2)
        finally:
            import os
            if os.path.exists(save_path):
                os.remove(save_path)

    def test_09_legacy_save_loading_without_selected_choices(self) -> None:
        """Save data without selected_choices field defaults cleanly to empty dict."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        serialized = serialize_player(self.player)

        # Simulate legacy save data (remove selected_choices key)
        del serialized["quests"]["first_encounter"]["selected_choices"]
        self.assertNotIn("selected_choices", serialized["quests"]["first_encounter"])

        restored = deserialize_player(serialized, quest_catalog=self.quest_manager.catalog)
        self.assertIn("first_encounter", restored.quests)
        prog = restored.quests["first_encounter"]
        self.assertEqual(prog.selected_choices, {})

    # --- 7. Representative Quests ---

    def test_10_representative_shrine_investigation_peaceful_path(self) -> None:
        """Full walkthrough of SHRINE_INVESTIGATION: peaceful offering branch."""
        # Player accepts First Encounter then Shrine Investigation
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        self.assertEqual(self.quest_manager.get_quest_status(self.player, "shrine_investigation"), QuestStatus.AVAILABLE)
        self.quest_manager.accept_quest(self.player, "shrine_investigation")

        prog = self.player.quests["shrine_investigation"]
        # Choice is gated behind obj_reach_shrine
        self.assertFalse(self.quest_manager.is_choice_available(self.player, "shrine_investigation", "investigation_path"))

        # Step 1: Discover Ancient Shrine landmark
        self.quest_manager.record_event(
            self.player,
            QuestEventType.LANDMARK_DISCOVERED,
            {"landmark_id": "ancient_shrine"},
        )
        self.assertTrue(prog.is_objective_completed("obj_reach_shrine"))

        # Choice is now available!
        self.assertTrue(self.quest_manager.is_choice_available(self.player, "shrine_investigation", "investigation_path"))

        # Step 2: Choose 'peaceful_offering'
        res = self.quest_manager.make_choice(self.player, "shrine_investigation", "investigation_path", "peaceful_offering")
        self.assertTrue(res.success)
        self.assertEqual(prog.get_selected_option("investigation_path"), "peaceful_offering")

        # Active objectives now include shrine inspection and potion gathering
        self.assertIn("obj_shrine_inspect", prog.objective_progress)
        self.assertIn("obj_shrine_potions", prog.objective_progress)
        self.assertNotIn("obj_shrine_combat", prog.objective_progress)

        # Step 3: Fulfill peaceful objectives
        self.quest_manager.record_event(
            self.player,
            QuestEventType.OBJECT_INTERACTED,
            {"object_id": "shrine_thunder_stone", "region_id": "ancient_shrine"},
        )
        self.assertTrue(prog.is_objective_completed("obj_shrine_inspect"))

        self.player.inventory.add_item("potion", 2)
        self.quest_manager.record_event(
            self.player,
            QuestEventType.ITEM_COLLECTED,
            {"item_id": "potion", "quantity": 2},
        )
        self.assertTrue(prog.is_objective_completed("obj_shrine_potions"))

        # Quest completed!
        self.assertTrue(prog.is_completed)
        self.assertEqual(prog.status, QuestStatus.COMPLETED)

        # Claim rewards: base potion: 1 + peaceful (antidote: 2, potion: 1) -> potion: 4, antidote: 2
        claim_res = self.quest_manager.claim_rewards(self.player, "shrine_investigation")
        self.assertTrue(claim_res.success)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 4)
        self.assertEqual(self.player.inventory.get_quantity("antidote"), 2)

    def test_11_representative_shrine_investigation_combat_path(self) -> None:
        """Full walkthrough of SHRINE_INVESTIGATION: combat trial branch."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        self.quest_manager.accept_quest(self.player, "shrine_investigation")
        prog = self.player.quests["shrine_investigation"]

        # Discover shrine
        self.quest_manager.advance_objective(self.player, "shrine_investigation", "obj_reach_shrine", 1)

        # Choose 'combat_trial'
        res = self.quest_manager.make_choice(self.player, "shrine_investigation", "investigation_path", "combat_trial")
        self.assertTrue(res.success)

        self.assertIn("obj_shrine_combat", prog.objective_progress)
        self.assertNotIn("obj_shrine_inspect", prog.objective_progress)
        self.assertNotIn("obj_shrine_potions", prog.objective_progress)

        # Defeat 2 Pokemon in ancient_shrine
        self.quest_manager.record_event(
            self.player,
            QuestEventType.POKEMON_DEFEATED,
            {"species": "Pikachu", "count": 2, "region_id": "ancient_shrine"},
        )
        self.assertTrue(prog.is_completed)

        # Rewards: base potion: 1 + combat super_potion: 2
        claim_res = self.quest_manager.claim_rewards(self.player, "shrine_investigation")
        self.assertTrue(claim_res.success)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 1)
        self.assertEqual(self.player.inventory.get_quantity("super_potion"), 2)

    def test_12_representative_research_specialization_immediate_choice(self) -> None:
        """Full walkthrough of RESEARCH_SPECIALIZATION: immediate choice upon acceptance."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        self.quest_manager.accept_quest(self.player, "research_specialization")
        prog = self.player.quests["research_specialization"]

        # Immediate choice is available right upon acceptance
        self.assertTrue(self.quest_manager.is_choice_available(self.player, "research_specialization", "specialization_branch"))

        # Choose 'field_capture'
        res = self.quest_manager.make_choice(self.player, "research_specialization", "specialization_branch", "field_capture")
        self.assertTrue(res.success)

        self.assertIn("obj_spec_capture", prog.objective_progress)
        self.assertNotIn("obj_spec_defeat", prog.objective_progress)

        # Capturing in starting meadow advances objective
        self.quest_manager.record_event(
            self.player,
            QuestEventType.POKEMON_CAPTURED,
            {"species": "Pikachu", "count": 2, "region_id": "starting_meadow"},
        )
        self.assertTrue(prog.is_completed)

        # Rewards: base potion: 1 + poke_ball: 3
        claim_res = self.quest_manager.claim_rewards(self.player, "research_specialization")
        self.assertTrue(claim_res.success)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 1)
        self.assertEqual(self.player.inventory.get_quantity("poke_ball"), 3)

    # --- 8. Journal Presentation of Branching Quests ---

    def test_13_quest_journal_dossier_displays_chosen_path(self) -> None:
        """QuestJournal dossier formatting displays the chosen path and active branch objectives."""
        journal = QuestJournal(quest_manager=self.quest_manager)
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        self.quest_manager.accept_quest(self.player, "research_specialization")
        self.quest_manager.make_choice(self.player, "research_specialization", "specialization_branch", "field_capture")

        entry = journal.get_entry(self.player, "research_specialization")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.chosen_paths, ["Field Capture Specialist"])

        dossier = journal.format_quest_dossier(entry)
        dossier_text = "\n".join(dossier)
        self.assertIn("Chosen Path  : Field Capture Specialist", dossier_text)
        self.assertIn("Capture 2 wild Pokémon in Starting Meadow", dossier_text)
        self.assertNotIn("Tactical Combat Specialist", dossier_text)

    # --- 9. NPC Dialogue Flow Integration ---

    def test_14_npc_dialogue_flow_choice_selection(self) -> None:
        """Simulate interacting with an NPC to accept a quest, make a choice, and verify dialogue."""
        inputs = [
            "3",  # Choose Research Specialization topic from Oak
            "1",  # Accept Quest
            "1",  # Choose option 1: Field Capture Specialist (prompted immediately)
            "0",  # Leave conversation
            "3",  # Exit game
        ]
        outputs: list[str] = []

        # Prerequisite
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        game = AdventureGame(
            input_fn=lambda prompt="": inputs.pop(0) if inputs else "3",
            output_fn=lambda *args: outputs.append(" ".join(str(a) for a in args)),
        )
        game.player = self.player
        game.quest_manager = self.quest_manager

        oak_obj = game.world_interaction_manager.get_object("npc_prof_oak")
        self.assertIsNotNone(oak_obj)

        # Trigger interaction
        res = game.world_interaction_manager.interact(
            player=self.player,
            object_id="npc_prof_oak",
            player_position=(2.5, 1.5),
            quest_manager=self.quest_manager,
        )
        self.assertTrue(res.success)

        # Run dialogue flow
        game._npc_dialogue_flow(oak_obj, res)

        full_output = "\n".join(outputs)
        self.assertIn("Selected path: 'Field Capture Specialist'", full_output)
        self.assertIn("A patient observer!", full_output)

        prog = self.player.quests["research_specialization"]
        self.assertEqual(prog.get_selected_option("specialization_branch"), "field_capture")
        self.assertIn("obj_spec_capture", prog.objective_progress)

    def test_15_regression_immediate_choice_on_acceptance(self) -> None:
        """Verify that accepting research_specialization immediately prompts for branch choice in same interaction."""
        inputs = [
            "3",  # Choose Research Specialization topic from Oak
            "1",  # Accept Quest
            "2",  # Immediately choose option 2: Tactical Combat Specialist
            "0",  # Leave conversation
        ]
        outputs: list[str] = []

        # Prerequisite
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        game = AdventureGame(
            input_fn=lambda prompt="": inputs.pop(0) if inputs else "0",
            output_fn=lambda *args: outputs.append(" ".join(str(a) for a in args)),
        )
        game.player = self.player
        game.quest_manager = self.quest_manager

        oak_obj = game.world_interaction_manager.get_object("npc_prof_oak")
        self.assertIsNotNone(oak_obj)

        res = game.world_interaction_manager.interact(
            player=self.player,
            object_id="npc_prof_oak",
            player_position=(2.5, 1.5),
            quest_manager=self.quest_manager,
        )
        self.assertTrue(res.success)

        game._npc_dialogue_flow(oak_obj, res)

        full_output = "\n".join(outputs)
        # Choice prompt was shown immediately without re-talking to NPC
        self.assertIn("Which field research discipline do you wish to pursue?", full_output)
        self.assertIn("Selected path: 'Tactical Combat Specialist'", full_output)
        self.assertIn("A spirited battle strategist!", full_output)

        prog = self.player.quests["research_specialization"]
        self.assertEqual(prog.get_selected_option("specialization_branch"), "tactical_combat")
        self.assertIn("obj_spec_defeat", prog.objective_progress)
        self.assertNotIn("obj_spec_capture", prog.objective_progress)

    def test_16_regression_immediate_choice_decide_later(self) -> None:
        """Verify that choosing 'Decide Later' (0) upon acceptance leaves choice uncommitted and reprompts later."""
        inputs = [
            "3",  # Choose Research Specialization topic from Oak
            "1",  # Accept Quest
            "0",  # Decide Later on immediate choice prompt
            "3",  # Select Research Specialization again from topic menu
            "1",  # Now choose Option 1: Field Capture Specialist
            "0",  # Leave conversation
        ]
        outputs: list[str] = []

        # Prerequisite
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        game = AdventureGame(
            input_fn=lambda prompt="": inputs.pop(0) if inputs else "0",
            output_fn=lambda *args: outputs.append(" ".join(str(a) for a in args)),
        )
        game.player = self.player
        game.quest_manager = self.quest_manager

        oak_obj = game.world_interaction_manager.get_object("npc_prof_oak")
        self.assertIsNotNone(oak_obj)

        res = game.world_interaction_manager.interact(
            player=self.player,
            object_id="npc_prof_oak",
            player_position=(2.5, 1.5),
            quest_manager=self.quest_manager,
        )
        self.assertTrue(res.success)

        game._npc_dialogue_flow(oak_obj, res)

        full_output = "\n".join(outputs)
        self.assertIn("You decided to consider your options before choosing.", full_output)
        self.assertIn("Selected path: 'Field Capture Specialist'", full_output)

        prog = self.player.quests["research_specialization"]
        self.assertEqual(prog.get_selected_option("specialization_branch"), "field_capture")
        self.assertIn("obj_spec_capture", prog.objective_progress)

    def test_17_regression_prerequisite_gated_choice_not_prompted_immediately(self) -> None:
        """Verify that accepting shrine_investigation does not prompt for choice immediately because obj_reach_shrine is unmet."""
        inputs = [
            "2",  # Choose Shrine Investigation topic from Ranger Logan
            "1",  # Accept Quest
            "0",  # Leave conversation
        ]
        outputs: list[str] = []

        # Prerequisite
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.advance_objective(self.player, "first_encounter", "capture_first_pokemon", 1)

        game = AdventureGame(
            input_fn=lambda prompt="": inputs.pop(0) if inputs else "0",
            output_fn=lambda *args: outputs.append(" ".join(str(a) for a in args)),
        )
        game.player = self.player
        game.quest_manager = self.quest_manager

        ranger_obj = game.world_interaction_manager.get_object("npc_trail_ranger")
        self.assertIsNotNone(ranger_obj)

        res = game.world_interaction_manager.interact(
            player=self.player,
            object_id="npc_trail_ranger",
            player_position=(25.5, 24.5),
            quest_manager=self.quest_manager,
        )
        self.assertTrue(res.success)

        game._npc_dialogue_flow(ranger_obj, res)

        full_output = "\n".join(outputs)
        self.assertIn("Accepted quest: 'Shrine Investigation'", full_output)
        # Choice prompt must NOT have been shown
        self.assertNotIn("How will you handle the shrine disturbance?", full_output)
        self.assertNotIn("Peaceful Offering", full_output)
        self.assertNotIn("Combat Trial", full_output)

        prog = self.player.quests["shrine_investigation"]
        self.assertEqual(prog.status, QuestStatus.ACTIVE)
        self.assertEqual(prog.selected_choices, {})
        self.assertIn("obj_reach_shrine", prog.objective_progress)


if __name__ == "__main__":
    unittest.main()
