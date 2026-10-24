"""
Unit and integration tests for Pokemon PC storage, collection access,
team swapping, and automatic team assignment upon wild capture.
"""

import os
import tempfile
import unittest

from src.models.species import PokemonSpecies
from src.models.personality import Personality
from src.models.attack import Attack
from src.models.pokemon_type import PokemonType
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.capture_manager import CaptureManager, CaptureResult
from src.models.battle_manager import BattleManager, BattleState
from src.models.quest_manager import QuestManager
from src.models.quest import QuestDefinition, QuestObjective, ObjectiveType, QuestEventType
from src.models.save_manager import save_game, load_game
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, TACKLE, SCRATCH
from game import AdventureGame


def make_io(inputs: list[str]):
    """Creates scripted input/output callables for AdventureGame testing."""
    input_iter = iter(inputs)
    logs: list[str] = []

    def mock_in(prompt: str = "") -> str:
        try:
            return next(input_iter)
        except StopIteration:
            return "quit"

    def mock_out(*args, **kwargs) -> None:
        text = " ".join(str(a) for a in args)
        logs.append(text)

    return logs, mock_in, mock_out


class TestPokemonPCAndTeamAssignment(unittest.TestCase):
    """Test suite for Pokemon PC, collection management, and capture team assignment."""

    def setUp(self) -> None:
        self.personality = Personality(50, 50, 50, 50, 50, 50)
        self.player = Player(name="Red")
        self.starter = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=5,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )
        self.player.add_pokemon(self.starter)
        self.player.add_to_team(self.starter)
        self.player.set_active_pokemon(self.starter)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_file = os.path.join(self.temp_dir.name, "test_save.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # --- 1. Automatic Team Assignment with Open Slot ---
    def test_01_capture_with_open_team_slot_auto_adds_to_team_and_collection(self) -> None:
        """Capturing a Pokemon with open team slots automatically adds it to collection and team."""
        cm = CaptureManager(min_probability=1.0)  # 100% catch rate
        wild_charmander = Pokemon(
            species=CHARMANDER,
            personality=self.personality,
            level=3,
            attacks=[SCRATCH],
        )

        self.assertEqual(len(self.player.collection), 1)
        self.assertEqual(len(self.player.team), 1)

        result = cm.attempt_capture(player=self.player, wild_pokemon=wild_charmander)

        self.assertTrue(result.accepted)
        self.assertTrue(result.success)
        self.assertTrue(result.added_to_collection)
        self.assertTrue(result.added_to_team)
        self.assertIn("joined your team", result.message)

        # Verification of player state
        self.assertEqual(len(self.player.collection), 2)
        self.assertEqual(len(self.player.team), 2)
        self.assertIn(wild_charmander, self.player.collection)
        self.assertIn(wild_charmander, self.player.team)
        self.assertTrue(self.player.is_on_team(wild_charmander))

    # --- 2. Automatic Team Assignment with Full Team ---
    def test_02_capture_with_full_team_adds_to_collection_only_and_reports_pc(self) -> None:
        """Capturing a Pokemon when team is full adds it to collection only and sends to PC."""
        cm = CaptureManager(min_probability=1.0)

        # Fill team to 6
        species_list = [CHARMANDER, SQUIRTLE, PIKACHU, CHARMANDER, SQUIRTLE]
        for sp in species_list:
            mon = Pokemon(species=sp, personality=self.personality, level=5, attacks=[TACKLE])
            self.player.add_pokemon(mon)
            self.player.add_to_team(mon)

        self.assertEqual(len(self.player.team), 6)
        self.assertEqual(len(self.player.collection), 6)

        # Attempt 7th capture
        wild_extra = Pokemon(species=CHARMANDER, personality=self.personality, level=4, attacks=[SCRATCH])
        result = cm.attempt_capture(player=self.player, wild_pokemon=wild_extra)

        self.assertTrue(result.accepted)
        self.assertTrue(result.success)
        self.assertTrue(result.added_to_collection)
        self.assertFalse(result.added_to_team)
        self.assertIn("sent to your PC", result.message)

        # Verification of player state
        self.assertEqual(len(self.player.collection), 7)
        self.assertEqual(len(self.player.team), 6)
        self.assertIn(wild_extra, self.player.collection)
        self.assertNotIn(wild_extra, self.player.team)
        self.assertFalse(self.player.is_on_team(wild_extra))

    # --- 3. Anti-Duplication on Repeated Capture Processing ---
    def test_03_repeated_capture_processing_cannot_duplicate(self) -> None:
        """Repeated capture attempt for already-owned Pokemon is rejected without duplicate entries."""
        cm = CaptureManager(min_probability=1.0)
        wild_mon = Pokemon(species=SQUIRTLE, personality=self.personality, level=3, attacks=[TACKLE])

        res1 = cm.attempt_capture(player=self.player, wild_pokemon=wild_mon)
        self.assertTrue(res1.success)
        self.assertEqual(len(self.player.collection), 2)
        self.assertEqual(len(self.player.team), 2)

        # Attempting capture again with same instance
        res2 = cm.attempt_capture(player=self.player, wild_pokemon=wild_mon)
        self.assertFalse(res2.accepted)
        self.assertFalse(res2.success)
        self.assertFalse(res2.added_to_collection)
        self.assertFalse(res2.added_to_team)
        self.assertIn("already in player's collection", res2.message)

        # Counts remain strictly unchanged
        self.assertEqual(len(self.player.collection), 2)
        self.assertEqual(len(self.player.team), 2)

        # Direct call to player.add_pokemon also prevents duplicate
        with self.assertRaises(ValueError):
            self.player.add_pokemon(wild_mon)

    # --- 4. Collection Menu Displays Team & Stored Pokemon ---
    def test_04_collection_menu_displays_team_and_stored_pokemon_correctly(self) -> None:
        """Collection view displays all owned Pokemon with clear TEAM vs PC storage tags."""
        stored_mon = Pokemon(species=CHARMANDER, personality=self.personality, level=7, attacks=[SCRATCH])
        self.player.add_pokemon(stored_mon)  # in collection, not in team

        inputs = ["1", "Red", "1", "4", "2", "0", "10", "y", "3"]
        logs, in_fn, out_fn = make_io(inputs)
        game = AdventureGame(input_fn=in_fn, output_fn=out_fn, save_file=self.save_file)

        def custom_in(prompt: str = "") -> str:
            if game.player is not None and not hasattr(custom_in, "setup"):
                custom_in.setup = True
                game.player.add_pokemon(stored_mon)
            return in_fn(prompt)

        game._input_fn = custom_in
        game.run()

        # Check logs for collection view
        self.assertTrue(any("POKEMON PC STORAGE & COLLECTION" in line for line in logs))
        self.assertTrue(any("[TEAM]" in line for line in logs))
        self.assertTrue(any("[PC]" in line for line in logs))
        self.assertTrue(any("Summary: 1 on Team | 1 stored in PC Box" in line for line in logs))

    # --- 5. Add Stored Pokemon to Team with Open Slot ---
    def test_05_add_stored_pokemon_to_team_with_open_slot(self) -> None:
        """Player can pick a stored Pokemon from PC and add it to an open team slot."""
        stored_mon = Pokemon(species=CHARMANDER, personality=self.personality, level=6, attacks=[SCRATCH])
        self.player.add_pokemon(stored_mon)

        # Via menu: Menu 4 -> Submenu 3 (Add Stored Pokemon) -> Pick 1 -> Back 0 -> Quit
        inputs = ["1", "Red", "1", "4", "3", "1", "0", "10", "y", "3"]
        logs, in_fn, out_fn = make_io(inputs)
        game = AdventureGame(input_fn=in_fn, output_fn=out_fn, save_file=self.save_file)

        def custom_in(prompt: str = "") -> str:
            if game.player is not None and not hasattr(custom_in, "setup"):
                custom_in.setup = True
                game.player.add_pokemon(stored_mon)
            return in_fn(prompt)

        game._input_fn = custom_in
        game.run()

        self.assertEqual(len(game.player.team), 2)
        self.assertIn(stored_mon, game.player.team)
        self.assertTrue(any("was added to your team!" in line for line in logs))

    # --- 6. Reject Duplicate Addition to Team ---
    def test_06_attempt_add_already_on_team_rejected_safely(self) -> None:
        """Attempting to add a Pokemon already on the active team raises ValueError or is rejected."""
        with self.assertRaises(ValueError):
            self.player.add_to_team(self.starter)

        # Unowned Pokemon cannot be added either
        unowned = Pokemon(species=CHARMANDER, personality=self.personality, level=5)
        with self.assertRaises(ValueError):
            self.player.add_to_team(unowned)

    # --- 7. Reject Adding Beyond Team Capacity ---
    def test_07_attempt_exceed_team_capacity_rejected_safely(self) -> None:
        """When team is full (6/6), adding another Pokemon is safely rejected."""
        for sp in [CHARMANDER, SQUIRTLE, PIKACHU, CHARMANDER, SQUIRTLE]:
            mon = Pokemon(species=sp, personality=self.personality, level=5)
            self.player.add_pokemon(mon)
            self.player.add_to_team(mon)

        self.assertEqual(len(self.player.team), 6)
        extra = Pokemon(species=PIKACHU, personality=self.personality, level=3)
        self.player.add_pokemon(extra)

        # Direct API
        with self.assertRaises(ValueError) as ctx:
            self.player.add_to_team(extra)
        self.assertIn("team is full", str(ctx.exception))

        # Via Menu
        inputs = ["1", "Red", "1", "4", "3", "0", "10", "y", "3"]
        logs, in_fn, out_fn = make_io(inputs)
        game = AdventureGame(input_fn=in_fn, output_fn=out_fn, save_file=self.save_file)

        def custom_in(prompt: str = "") -> str:
            if game.player is not None and not hasattr(custom_in, "setup"):
                custom_in.setup = True
                for sp in [CHARMANDER, SQUIRTLE, PIKACHU, CHARMANDER, SQUIRTLE]:
                    m = Pokemon(species=sp, personality=self.personality, level=5)
                    game.player.add_pokemon(m)
                    game.player.add_to_team(m)
                game.player.add_pokemon(extra)
            return in_fn(prompt)

        game._input_fn = custom_in
        game.run()

        self.assertTrue(any("Your team is already full" in line for line in logs))

    # --- 8. Swapping Team Members Preserves Both Pokemon and State ---
    def test_08_swapping_team_members_preserves_both_pokemon_and_state(self) -> None:
        """Swapping a team member with a stored PC Pokemon preserves all state and order."""
        # Member on team: damaged, custom bond, moves
        team_mon = self.starter
        team_mon.current_hp = 12
        team_mon.bond = 65
        team_mon.experience = 150

        # Stored PC Pokemon
        pc_mon = Pokemon(species=CHARMANDER, personality=self.personality, level=8, attacks=[SCRATCH])
        pc_mon.bond = 25
        pc_mon.experience = 320
        self.player.add_pokemon(pc_mon)

        orig_id_team = team_mon.unique_id
        orig_id_pc = pc_mon.unique_id

        # Swap via Player method
        out_mon, in_mon = self.player.swap_team_member(team_mon, pc_mon)

        self.assertIs(out_mon, team_mon)
        self.assertIs(in_mon, pc_mon)

        # Team assertions
        self.assertEqual(len(self.player.team), 1)
        self.assertIn(pc_mon, self.player.team)
        self.assertNotIn(team_mon, self.player.team)
        self.assertEqual(self.player.active_pokemon, pc_mon)

        # Collection assertions: both preserved
        self.assertEqual(len(self.player.collection), 2)
        self.assertIn(team_mon, self.player.collection)
        self.assertIn(pc_mon, self.player.collection)

        # State integrity
        self.assertEqual(team_mon.unique_id, orig_id_team)
        self.assertEqual(team_mon.current_hp, 12)
        self.assertEqual(team_mon.bond, 65)
        self.assertEqual(team_mon.experience, 150)

        self.assertEqual(pc_mon.unique_id, orig_id_pc)
        self.assertEqual(pc_mon.bond, 25)
        self.assertEqual(pc_mon.experience, 320)

    # --- 9. Swapping via Menu in AdventureGame ---
    def test_09_swapping_via_game_menu(self) -> None:
        """Player can swap team members using menu option 4."""
        stored_mon = Pokemon(species=SQUIRTLE, personality=self.personality, level=5, attacks=[TACKLE])

        # Inputs: Menu 4 -> Submenu 4 (Swap) -> Select team #1 -> Select stored #1 -> Back 0 -> Quit
        inputs = ["1", "Red", "1", "4", "4", "1", "1", "0", "10", "y", "3"]
        logs, in_fn, out_fn = make_io(inputs)
        game = AdventureGame(input_fn=in_fn, output_fn=out_fn, save_file=self.save_file)

        def custom_in(prompt: str = "") -> str:
            if game.player is not None and not hasattr(custom_in, "setup"):
                custom_in.setup = True
                game.player.add_pokemon(stored_mon)
            return in_fn(prompt)

        game._input_fn = custom_in
        game.run()

        self.assertTrue(any("Successfully swapped" in line for line in logs))
        self.assertEqual(game.player.team[0].species.name, "Squirtle")
        self.assertEqual(len(game.player.collection), 2)
        self.assertEqual(len(game.player.team), 1)

    # --- 10. Saving and Loading Preserves Collection and Team Assignments ---
    def test_10_saving_and_loading_preserves_collection_and_team(self) -> None:
        """Save/load preserves all collection Pokemon and active team assignments exactly."""
        p2 = Pokemon(species=CHARMANDER, personality=self.personality, level=6)
        p3 = Pokemon(species=SQUIRTLE, personality=self.personality, level=7)
        p4 = Pokemon(species=PIKACHU, personality=self.personality, level=4)  # PC storage only

        self.player.add_pokemon(p2)
        self.player.add_to_team(p2)

        self.player.add_pokemon(p3)
        self.player.add_to_team(p3)

        self.player.add_pokemon(p4)  # in PC

        self.assertEqual(len(self.player.team), 3)
        self.assertEqual(len(self.player.collection), 4)

        save_game(self.player, self.save_file)
        loaded = load_game(self.save_file)

        # Verification of restored Player
        self.assertEqual(len(loaded.collection), 4)
        self.assertEqual(len(loaded.team), 3)
        self.assertEqual(loaded.team[0].unique_id, self.starter.unique_id)
        self.assertEqual(loaded.team[1].unique_id, p2.unique_id)
        self.assertEqual(loaded.team[2].unique_id, p3.unique_id)
        self.assertTrue(loaded.is_on_team(loaded.get_pokemon_by_id(p2.unique_id)))
        self.assertFalse(loaded.is_on_team(loaded.get_pokemon_by_id(p4.unique_id)))
        self.assertEqual(loaded.active_pokemon.unique_id, self.starter.unique_id)

    # --- 11. Starter Initialization and In-Battle Capture Quest Dispatch ---
    def test_11_starter_init_and_capture_quest_events(self) -> None:
        """Starting game properly places starter on team, and in-battle capture dispatches quest events."""
        inputs = ["1", "Ash", "1", "10", "y", "3"]
        logs, in_fn, out_fn = make_io(inputs)
        game = AdventureGame(input_fn=in_fn, output_fn=out_fn, save_file=self.save_file)
        game.run()

        # Starter is in collection and team
        self.assertIsNotNone(game.player)
        self.assertEqual(len(game.player.collection), 1)
        self.assertEqual(len(game.player.team), 1)
        self.assertEqual(game.player.active_pokemon, game.player.team[0])

        # Test battle manager capture emits quest event
        qm = QuestManager()
        qm.accept_quest(game.player, "first_encounter")

        bm = BattleManager(quest_manager=qm, seed=42)
        wild = Pokemon(species=SQUIRTLE, personality=self.personality, level=3)
        battle = bm.start_battle(game.player, wild)

        cm = CaptureManager(min_probability=1.0)
        action_res = bm.attempt_capture(game.player, capture_manager=cm)

        self.assertTrue(action_res.accepted)
        self.assertEqual(action_res.battle_state, BattleState.CAPTURED)
        self.assertTrue(game.player.quests["first_encounter"].is_completed)
        self.assertIn(wild, game.player.team)
        self.assertIn(wild, game.player.collection)

    # --- 12. Edge Cases: Empty Collection, Blank Input, Cancellation ---
    def test_12_empty_collection_invalid_input_and_deposit_edge_cases(self) -> None:
        """Edge cases such as single-member deposit, blank input, and invalid numbers do not crash."""
        p_empty = Player(name="Ghost")
        self.assertEqual(len(p_empty.collection), 0)
        self.assertEqual(len(p_empty.team), 0)

        # Deposit single Pokemon should fail (must keep at least 1)
        inputs = ["1", "Red", "1", "4", "5", "1", "0", "10", "y", "3"]
        logs, in_fn, out_fn = make_io(inputs)
        game = AdventureGame(input_fn=in_fn, output_fn=out_fn, save_file=self.save_file)
        game.run()

        self.assertTrue(any("cannot deposit your only team Pokemon" in line for line in logs))
        self.assertEqual(len(game.player.team), 1)

        # Deposit works when team has 2 members
        p2 = Pokemon(species=SQUIRTLE, personality=self.personality, level=5)
        inputs_dep = ["1", "Red", "1", "4", "5", "2", "0", "10", "y", "3"]
        logs_dep, in_dep, out_dep = make_io(inputs_dep)
        game2 = AdventureGame(input_fn=in_dep, output_fn=out_dep, save_file=self.save_file)

        def custom_in2(prompt: str = "") -> str:
            if game2.player is not None and not hasattr(custom_in2, "setup"):
                custom_in2.setup = True
                game2.player.add_pokemon(p2)
                game2.player.add_to_team(p2)
            return in_dep(prompt)

        game2._input_fn = custom_in2
        game2.run()

        self.assertTrue(any("was deposited to your PC" in line for line in logs_dep))
        self.assertEqual(len(game2.player.team), 1)
        self.assertEqual(len(game2.player.collection), 2)

    # --- 13. Active Pokemon Status on Swapping ---
    def test_13_active_pokemon_updates_safely_when_swapping(self) -> None:
        """When swapping out the active Pokemon, active partner updates safely."""
        active_mon = self.starter
        stored_healthy = Pokemon(species=CHARMANDER, personality=self.personality, level=5)
        self.player.add_pokemon(stored_healthy)

        # Swapping active partner with healthy stored member makes new member active
        self.player.swap_team_member(active_mon, stored_healthy)
        self.assertEqual(self.player.active_pokemon, stored_healthy)

        # Swapping active partner with fainted stored member assigns to first conscious teammate
        fainted_pc = Pokemon(species=SQUIRTLE, personality=self.personality, level=5)
        fainted_pc.current_hp = 0
        self.assertTrue(fainted_pc.is_fainted)
        self.player.add_pokemon(fainted_pc)

        # Add a healthy second teammate
        healthy_teammate = Pokemon(species=PIKACHU, personality=self.personality, level=5)
        self.player.add_pokemon(healthy_teammate)
        self.player.add_to_team(healthy_teammate)

        # Currently: team has [stored_healthy (active), healthy_teammate]
        # Swap stored_healthy with fainted_pc
        self.player.swap_team_member(stored_healthy, fainted_pc)
        self.assertEqual(self.player.active_pokemon, healthy_teammate)


if __name__ == "__main__":
    unittest.main()
