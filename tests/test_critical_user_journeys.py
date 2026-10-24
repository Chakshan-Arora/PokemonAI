"""
Comprehensive verification of the 10 Critical User Journeys for Syntax Error 2026.

Journeys:
1. Start a new game, select each available starter in separate runs, save, quit, and load.
2. Harvest a resource, return to the title screen, start a new game, and verify world objects reset.
3. Discover a region and landmark, collect a treasure, save, reload, and verify documented persistence.
4. Accept a capture quest, capture a wild Pokemon through the battle/game interface, verify quest progress.
5. Win, flee from, and capture wild encounters; confirm each battle ends cleanly without duplicate rewards.
6. Run a trainer battle with multiple Pokemon on both sides, including opponent status KO during switch.
7. Explore with all team members fainted and confirm there is no crash or endless loop.
8. Try invalid menu input, blank input, cancellation, and end-of-input; verify clean recovery/exit.
9. Attempt to load missing, corrupt, and unsupported save files; verify clear errors and atomic preservation.
10. Create two independent game instances and verify player, world objects, and managers do not leak.
"""
import os
import json
import tempfile
import unittest
from typing import Iterator

from game import AdventureGame
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.pokemon_type import PokemonType
from src.models.attack import Attack
from src.models.player import Player
from src.models.battle_state import BattleState
from src.models.battle import Battle, BattleAction, BattleActionType
from src.models.battle_manager import BattleManager
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager
from src.models.capture_manager import CaptureManager
from src.models.experience_manager import ExperienceManager
from src.models.quest_manager import QuestManager
from src.models.status_effect import StatusEffectType
from src.models.save_manager import save_game, load_game, CURRENT_SCHEMA_VERSION, SaveDataError
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH, WATER_GUN, TACKLE
from src.data.quests import FIRST_ENCOUNTER, WILD_CHALLENGER


def make_io(inputs: list[str]) -> tuple[list[str], callable, callable]:
    """Helper creating mock input and output functions."""
    it: Iterator[str] = iter(inputs)
    logs: list[str] = []

    def mock_input(prompt: str = "") -> str:
        try:
            return next(it)
        except StopIteration:
            return "quit"

    def mock_output(*args, **kwargs) -> None:
        logs.append(" ".join(str(a) for a in args))

    return logs, mock_input, mock_output


class TestCriticalUserJourneys(unittest.TestCase):
    """End-to-end verification of all 10 critical user journeys."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_file = os.path.join(self.temp_dir.name, "journey_save.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # --- Journey 1: All Starters (Bulbasaur, Charmander, Squirtle) New Game -> Save -> Quit -> Load ---
    def test_journey_01_all_starters_new_game_save_quit_load(self) -> None:
        """New game with Bulbasaur, Charmander, and Squirtle saves, quits, and restores accurately."""
        starters = [
            ("1", "Bulbasaur", "Bulby", ["Tackle", "Vine Whip"]),
            ("2", "Charmander", "Flamy", ["Scratch", "Ember"]),
            ("3", "Squirtle", "Shelly", ["Tackle", "Water Gun"]),
        ]

        for starter_idx, species_name, trainer_name, move_names in starters:
            save_path = os.path.join(self.temp_dir.name, f"starter_{species_name}.json")

            # 1. Start new game, save, return to title, quit
            # Menu inputs: [1] New Game -> Trainer Name -> Starter choice -> [9] Save -> [10] Title -> y -> [3] Quit
            inputs_new = ["1", trainer_name, starter_idx, "9", "10", "y", "3"]
            logs_new, in_fn_new, out_fn_new = make_io(inputs_new)
            game_new = AdventureGame(input_fn=in_fn_new, output_fn=out_fn_new, save_file=save_path)
            game_new.run()

            self.assertTrue(os.path.exists(save_path))
            self.assertEqual(game_new.player.name, trainer_name)
            self.assertEqual(game_new.player.active_pokemon.species.name, species_name)

            # 2. Load game from title screen, verify state, return to title, quit
            # Menu inputs: [2] Load Game -> [10] Title -> y -> [3] Quit
            inputs_load = ["2", "10", "y", "3"]
            logs_load, in_fn_load, out_fn_load = make_io(inputs_load)
            game_load = AdventureGame(input_fn=in_fn_load, output_fn=out_fn_load, save_file=save_path)
            game_load.run()

            self.assertIsNotNone(game_load.player)
            self.assertEqual(game_load.player.name, trainer_name)
            self.assertEqual(game_load.player.active_pokemon.species.name, species_name)
            self.assertEqual(game_load.player.active_pokemon.level, 5)
            self.assertEqual([a.name for a in game_load.player.active_pokemon.attacks], move_names)
            self.assertEqual(game_load.player.inventory.get_quantity("poke_ball"), 5)
            self.assertEqual(game_load.player.inventory.get_quantity("potion"), 3)

    # --- Journey 2: Harvest Resource -> Return to Title -> New Game -> World Objects Reset ---
    def test_journey_02_harvest_resource_title_reset(self) -> None:
        """Depleting a resource node in session 1 resets cleanly when starting new game in session 2."""
        # Session 1: New Game -> Interact with Berry Bush (5.0, 5.0) -> Return to Title
        # Session 2: New Game -> Check Berry Bush is available -> Return to Title -> Quit
        inputs = [
            # Session 1
            "1", "Ash", "1",
            "3", "1",          # Interact with Berry Bush (grants 1x potion, becomes depleted)
            "10", "y",         # Return to Title menu
            # Session 2
            "1", "Gary", "2",
            "3", "1",          # Interact with Berry Bush again (must succeed because objects reset!)
            "10", "y",
            "3",               # Quit
        ]
        logs, in_fn, out_fn = make_io(inputs)
        game = AdventureGame(input_fn=in_fn, output_fn=out_fn, save_file=self.save_file)
        game.run()

        # Both interactions should have succeeded!
        acquired_lines = [line for line in logs if "Acquired: 1x potion" in line]
        self.assertEqual(len(acquired_lines), 2)
        self.assertEqual(game.player.name, "Gary")
        self.assertEqual(game.player.inventory.get_quantity("potion"), 4)  # 3 starting + 1 gathered

    # --- Journey 3: Discover Region & Landmark, Collect Treasure -> Save -> Reload ---
    def test_journey_03_discover_region_landmark_treasure_persistence(self) -> None:
        """Exploration discoveries and treasure loots persist across save/load round trip."""
        # Session 1:
        # Travel to Forest Trail (2 -> 3), loot supply cache (3 -> 1 in range)
        # Travel to Ancient Shrine (2 -> 4), discover shrine (3 -> 1 in range)
        # Save (9) -> Title (10 -> y) -> Quit (3)
        inputs1 = [
            "1", "Explorer Red", "1",
            "2", "3",
            "3", "1",
            "2", "4",
            "3", "1",
            "9",
            "10", "y",
            "3",
        ]
        logs1, in_fn1, out_fn1 = make_io(inputs1)
        game1 = AdventureGame(input_fn=in_fn1, output_fn=out_fn1, save_file=self.save_file)
        game1.run()

        self.assertTrue(game1.player.is_treasure_collected("supply_cache_01"))
        self.assertTrue(game1.player.is_landmark_discovered("ancient_shrine"))
        self.assertTrue(game1.player.is_region_discovered("ancient_shrine_grounds"))

        # Session 2: Load game and verify persistence
        inputs2 = ["2", "10", "y", "3"]
        logs2, in_fn2, out_fn2 = make_io(inputs2)
        game2 = AdventureGame(input_fn=in_fn2, output_fn=out_fn2, save_file=self.save_file)
        game2.run()

        self.assertEqual(game2.player.name, "Explorer Red")
        self.assertTrue(game2.player.is_treasure_collected("supply_cache_01"))
        self.assertTrue(game2.player.is_landmark_discovered("ancient_shrine"))
        self.assertTrue(game2.player.is_region_discovered("ancient_shrine_grounds"))
        # Waypoint placed at furthest discovered region (ancient_shrine_grounds: 25.0, 25.0)
        self.assertEqual(game2.current_region_id, "ancient_shrine_grounds")
        self.assertEqual(game2.player_pos, [25.0, 25.0])
        # Clock safely reset to midday
        self.assertEqual(game2.game_hour, 12.0)

    # --- Journey 4: Accept Capture Quest -> Capture in Battle -> Verify Quest & Collection ---
    def test_journey_04_quest_in_game_battle_capture(self) -> None:
        """In-battle capture through actual interface advances and completes First Encounter quest."""
        # 1. New Game -> Quests (6) -> Accept (1) -> First Encounter (1) -> Back (0)
        # 2. Explore (1) -> Encounter triggered -> Throw Poke Ball (3) -> (Captured!)
        # 3. Quests (6) -> Claim (2) -> Back (0) -> Title (10 -> y) -> Quit (3)
        inputs = [
            "1", "Ash", "1",
            "6", "1", "1", "0",  # Accept First Encounter quest
            "1",                  # Explore
            "3",                  # Throw Poke Ball
            "6", "2", "0",        # Claim completed quest reward
            "10", "y", "3",
        ]
        logs, in_fn, out_fn = make_io(inputs)
        # Use seed 42 to guarantee encounter and configure capture manager for 100% catch rate
        game = AdventureGame(input_fn=in_fn, output_fn=out_fn, save_file=self.save_file, seed=42)
        game.capture_manager._min_probability = 1.0  # Guarantees catch on first ball for test determinism
        game.run()

        # Verify capture succeeded
        self.assertTrue(any("Congratulations! You caught the wild" in line for line in logs))
        # Verify collection count grew from 1 to 2
        self.assertEqual(len(game.player.collection), 2)
        # Verify quest reward was claimed (First Encounter grants 3x poke_ball)
        self.assertTrue(any("Claimed rewards for 'First Encounter'" in line for line in logs))
        self.assertTrue(game.player.quests["first_encounter"].rewards_claimed)

    # --- Journey 5: Wild Battle Outcomes (Win, Flee, Capture) & Anti-Duplication ---
    def test_journey_05_wild_battle_outcomes_and_no_duplicate_rewards(self) -> None:
        """Win, flee, and capture conclude cleanly with zero duplicate rewards."""
        personality = Personality(50, 50, 50, 50, 50, 50)
        player = Player(name="Ash")
        pika = Pokemon(species=PIKACHU, personality=personality, level=5, attacks=[THUNDER_SHOCK])
        player.add_pokemon(pika)
        player.add_to_team(pika)
        player.set_active_pokemon(pika)

        bm = BattleManager(experience_manager=ExperienceManager(), seed=42)

        # 1. Victory
        wild1 = Pokemon(species=CHARMANDER, personality=personality, level=5, attacks=[EMBER])
        wild1.current_hp = 1
        b_win = bm.start_battle(player, wild1, use_random_damage=False)
        res_win = bm.attack(player, THUNDER_SHOCK)
        self.assertEqual(b_win.state, BattleState.VICTORY)
        xp_after = pika.experience
        self.assertGreater(xp_after, 0)
        # Attempt duplicate reward claim
        repeat_reward = bm._experience_manager.award_battle_rewards(b_win)
        self.assertFalse(repeat_reward.eligible)
        self.assertEqual(pika.experience, xp_after)

        # 2. Flee
        wild2 = Pokemon(species=SQUIRTLE, personality=personality, level=5, attacks=[WATER_GUN])
        b_flee = bm.start_battle(player, wild2)
        res_flee = bm.flee(player)
        self.assertEqual(b_flee.state, BattleState.ESCAPED)
        self.assertFalse(bm.has_active_battle(player))

        # 3. Capture
        wild3 = Pokemon(species=CHARMANDER, personality=personality, level=5, attacks=[EMBER])
        wild3.current_hp = 1
        b_cap = bm.start_battle(player, wild3)
        res_cap = bm.attempt_capture(player, capture_manager=CaptureManager(seed=1, min_probability=1.0))
        self.assertEqual(b_cap.state, BattleState.CAPTURED)
        self.assertFalse(bm.has_active_battle(player))
        self.assertIn(wild3, player.collection)

    # --- Journey 6: Multi-Pokemon Trainer Battle with Status KO on Switch ---
    def test_journey_06_trainer_battle_status_ko_during_switch(self) -> None:
        """Trainer battle opponent auto-switches when active Pokemon faints from poison during player switch."""
        personality = Personality(50, 50, 50, 50, 50, 50)
        player = Player(name="Ash")
        pika = Pokemon(species=PIKACHU, personality=personality, level=5, attacks=[THUNDER_SHOCK])
        squirt = Pokemon(species=SQUIRTLE, personality=personality, level=5, attacks=[WATER_GUN])
        player.add_pokemon(pika)
        player.add_pokemon(squirt)
        player.add_to_team(pika)
        player.add_to_team(squirt)
        player.set_active_pokemon(pika)

        rival = Player(name="Gary")
        char1 = Pokemon(species=CHARMANDER, personality=personality, level=5, attacks=[EMBER])
        char2 = Pokemon(species=SQUIRTLE, personality=personality, level=5, attacks=[WATER_GUN])
        rival.add_pokemon(char1)
        rival.add_pokemon(char2)
        rival.add_to_team(char1)
        rival.add_to_team(char2)
        rival.set_active_pokemon(char1)

        battle = Battle(
            pokemon1=pika,
            pokemon2=char1,
            player=player,
            opponent_trainer=rival,
            player_team=player.team,
            opponent_team=rival.team,
            seed=42,
        )
        battle.start()

        # Poison Gary's Charmander and drop HP to 1
        char1.current_hp = 1
        battle.status_manager.apply_effect(char1, StatusEffectType.POISON)

        # Player switches to Squirtle
        res_switch = battle.take_action(BattleAction(action_type=BattleActionType.SWITCH, target_pokemon=squirt))
        self.assertTrue(res_switch.accepted)
        self.assertTrue(char1.is_fainted)
        # Gary auto-switches to Squirtle
        self.assertIs(battle.pokemon2, char2)
        self.assertEqual(battle.state, BattleState.IN_PROGRESS)

        # Ash finishes the battle by defeating Gary's second Pokemon
        char2.current_hp = 1
        res_attack = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=WATER_GUN))
        self.assertTrue(char2.is_fainted)
        self.assertEqual(battle.state, BattleState.VICTORY)

    # --- Journey 7: Explore with All Team Members Fainted (No Crash/Loop) ---
    def test_journey_07_explore_with_all_fainted_team_safe(self) -> None:
        """Attempting to explore tall grass with an all-fainted team warns player without crashing."""
        inputs = [
            "1", "Ash", "1",
            "1",          # Explore (blocked by fainted team)
            "10", "y",
            "3",
        ]
        logs, in_fn, out_fn = make_io(inputs)
        game = AdventureGame(input_fn=in_fn, output_fn=out_fn, save_file=self.save_file)

        # Pre-faint player's starter as soon as game initializes
        def custom_input(prompt: str = "") -> str:
            if game.player is not None and game.player.active_pokemon is not None:
                game.player.active_pokemon.take_damage(game.player.active_pokemon.max_hp)
            return in_fn(prompt)

        game._input_fn = custom_input
        game.run()

        self.assertTrue(any("All Pokemon on your team have fainted" in line for line in logs))
        self.assertTrue(any("Heal your team with items or rest" in line for line in logs))
        self.assertFalse(game.battle_manager.has_active_battle(game.player))

    # --- Journey 8: Invalid Menu Input, Blanks, Cancellation, and End-of-Input ---
    def test_journey_08_invalid_input_blanks_cancellation_eof(self) -> None:
        """Game handles invalid inputs, blank inputs, cancellations, and EOF gracefully."""
        inputs = [
            "invalid_title",
            "",
            "   ",
            "99",
            "1",                  # Valid: New Game
            "Ash",
            "invalid_starter",
            "1",                  # Starter: Pikachu
            "",                   # Blank main menu choice
            "invalid_menu",       # Invalid menu choice
            "4", "0",             # Open Team (4) -> Cancel (0)
            "5", "0",             # Open Inventory (5) -> Cancel (0)
            "6", "0",             # Open Quests (6) -> Cancel (0)
            "10", "n",            # Title (10) -> Don't return (n)
            "10", "y",            # Title (10) -> Confirm (y)
            "3",                  # Quit
        ]
        logs, in_fn, out_fn = make_io(inputs)
        game = AdventureGame(input_fn=in_fn, output_fn=out_fn, save_file=self.save_file)
        game.run()

        self.assertFalse(game.is_running)
        self.assertTrue(any("Invalid choice 'invalid_title'" in line for line in logs))
        self.assertTrue(any("Please enter 1, 2, or 3" in line for line in logs))
        self.assertTrue(any("Returning to title menu" in line for line in logs))

    # --- Journey 9: Missing, Corrupt, and Unsupported Save Files ---
    def test_journey_09_missing_corrupt_unsupported_save_handling(self) -> None:
        """Loading missing, corrupt, or unsupported saves gives clear feedback and preserves files."""
        # 1. Missing file
        missing_path = os.path.join(self.temp_dir.name, "does_not_exist.json")
        logs1, in1, out1 = make_io(["2", "3"])
        game1 = AdventureGame(input_fn=in1, output_fn=out1, save_file=missing_path)
        game1.run()
        self.assertTrue(any("No save file found" in line for line in logs1))

        # 2. Corrupt JSON file
        corrupt_path = os.path.join(self.temp_dir.name, "corrupt.json")
        with open(corrupt_path, "w") as f:
            f.write("{not valid json at all!")
        logs2, in2, out2 = make_io(["2", "3"])
        game2 = AdventureGame(input_fn=in2, output_fn=out2, save_file=corrupt_path)
        game2.run()
        self.assertTrue(any("Failed to load save file" in line for line in logs2))
        # Verify corrupt file was not overwritten
        with open(corrupt_path, "r") as f:
            self.assertEqual(f.read(), "{not valid json at all!")

        # 3. Unsupported schema version
        unsupported_path = os.path.join(self.temp_dir.name, "unsupported_v99.json")
        with open(unsupported_path, "w") as f:
            json.dump({"schema_version": 99, "player": {"name": "Test"}}, f)
        logs3, in3, out3 = make_io(["2", "3"])
        game3 = AdventureGame(input_fn=in3, output_fn=out3, save_file=unsupported_path)
        game3.run()
        self.assertTrue(any("Failed to load save file" in line for line in logs3))

    # --- Journey 10: Two Independent Game Instances Isolation ---
    def test_journey_10_two_independent_game_instances_isolation(self) -> None:
        """Two independent game instances share no mutable state, managers, or objects."""
        # Game 1: Ash with Pikachu, harvests Berry Bush at (5.0, 5.0)
        inputs1 = ["1", "Ash", "1", "3", "1", "10", "y", "3"]
        logs1, in1, out1 = make_io(inputs1)
        game1 = AdventureGame(input_fn=in1, output_fn=out1, save_file=os.path.join(self.temp_dir.name, "s1.json"))
        game1.run()

        # Game 2: Misty with Squirtle, checks Berry Bush at (5.0, 5.0)
        inputs2 = ["1", "Misty", "3", "3", "1", "10", "y", "3"]
        logs2, in2, out2 = make_io(inputs2)
        game2 = AdventureGame(input_fn=in2, output_fn=out2, save_file=os.path.join(self.temp_dir.name, "s2.json"))
        game2.run()

        # Assert complete isolation
        self.assertEqual(game1.player.name, "Ash")
        self.assertEqual(game2.player.name, "Misty")
        self.assertEqual(game1.player.active_pokemon.species.name, "Bulbasaur")
        self.assertEqual(game2.player.active_pokemon.species.name, "Squirtle")
        # Berry Bush in Game 2 was available and harvested independently
        self.assertEqual(game2.player.inventory.get_quantity("potion"), 4)


if __name__ == "__main__":
    unittest.main()
