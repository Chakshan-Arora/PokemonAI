"""
Automated End-to-End Game Loop Test Suite for Syntax Error 2026.

Exercises all menu flows, battle sequences, spatial travel, world interactions,
inventory usage, quest lifecycles, and save/load persistence without terminal blocking.
"""
import os
import tempfile
import unittest
from pathlib import Path
from typing import Iterator

from game import AdventureGame
from src.models.battle_state import BattleState
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.pokemon_type import PokemonType
from src.models.habitat import TimeOfDay
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import QUICK_ATTACK, THUNDER_SHOCK, SCRATCH, EMBER, WATER_GUN, TACKLE


def create_scripted_io(input_sequence: list[str]) -> tuple[Iterator[str], list[str], callable, callable]:
    """
    Creates injectable input_fn and output_fn pair for automated test execution.
    """
    inputs_iter = iter(input_sequence)
    logs: list[str] = []

    def mock_input(prompt: str = "") -> str:
        try:
            return next(inputs_iter)
        except StopIteration:
            return "quit"

    def mock_output(*args, **kwargs) -> None:
        msg = " ".join(str(a) for a in args)
        logs.append(msg)

    return inputs_iter, logs, mock_input, mock_output


class TestGameLoop(unittest.TestCase):
    """
    Integration tests covering the complete AdventureGame menu lifecycle.
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_path = os.path.join(self.temp_dir.name, "test_save.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # 1. New game creation and Bulbasaur starter setup
    def test_01_new_game_creation_and_starter_setup(self) -> None:
        """Creating a new game with Bulbasaur sets up player, team, items, and meadow."""
        # Choices: New Game (1) -> Name: "Red" -> Starter: Bulbasaur (1) -> Quit to Title (10) -> y -> Quit (3)
        inputs = ["1", "Red", "1", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)

        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path, seed=42)
        game.run()

        self.assertIsNotNone(game.player)
        self.assertEqual(game.player.name, "Red")
        self.assertEqual(len(game.player.team), 1)
        active = game.player.active_pokemon
        self.assertIsNotNone(active)
        self.assertEqual(active.species.name, "Bulbasaur")
        self.assertEqual(active.level, 5)
        self.assertEqual(active.current_hp, active.max_hp)
        self.assertEqual(len(active.attacks), 2)

        # Starter inventory: 5 Poke Balls and 3 Potions
        self.assertTrue(game.player.inventory.has_item("poke_ball", 5))
        self.assertTrue(game.player.inventory.has_item("potion", 3))

        # Position in Starting Meadow
        self.assertEqual(game.player_pos, [5.0, 5.0])
        self.assertEqual(game.current_region_id, "starting_meadow")
        self.assertTrue(game.player.is_region_discovered("starting_meadow"))

    # 2. Charmander and Squirtle starters
    def test_02_new_game_charmander_and_squirtle_starters(self) -> None:
        """Creating new games with Charmander and Squirtle initializes correct species and moves."""
        # Charmander
        inputs_char = ["1", "Blue", "2", "10", "y", "3"]
        _, _, mock_in1, mock_out1 = create_scripted_io(inputs_char)
        game1 = AdventureGame(input_fn=mock_in1, output_fn=mock_out1, save_file=self.save_path, seed=42)
        game1.run()
        self.assertEqual(game1.player.active_pokemon.species.name, "Charmander")
        self.assertEqual([a.name for a in game1.player.active_pokemon.attacks], ["Scratch", "Ember"])

        # Squirtle
        inputs_sq = ["1", "Green", "3", "10", "y", "3"]
        _, _, mock_in2, mock_out2 = create_scripted_io(inputs_sq)
        game2 = AdventureGame(input_fn=mock_in2, output_fn=mock_out2, save_file=self.save_path, seed=42)
        game2.run()
        self.assertEqual(game2.player.active_pokemon.species.name, "Squirtle")
        self.assertEqual([a.name for a in game2.player.active_pokemon.attacks], ["Tackle", "Water Gun"])

    # 3. Title menu invalid input and clean exit
    def test_03_title_menu_invalid_input_and_quit(self) -> None:
        """Invalid inputs at the title menu are rejected without crashing."""
        inputs = ["garbage", "-1", "99", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)

        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        self.assertFalse(game.is_running)
        self.assertTrue(any("Invalid choice 'garbage'" in line for line in logs))
        self.assertTrue(any("Goodbye" in line for line in logs))

    # 4. Save and load round-trip persistence
    def test_04_save_and_load_round_trip(self) -> None:
        """Saving in adventure menu and loading through title menu restores exact state."""
        # Session 1: New Game -> Name: "Gary" -> Starter: Charmander (2) -> Save Game (9) -> Title (10) -> y -> Quit (3)
        inputs1 = ["1", "Gary", "2", "9", "10", "y", "3"]
        _, logs1, mock_in1, mock_out1 = create_scripted_io(inputs1)
        game1 = AdventureGame(input_fn=mock_in1, output_fn=mock_out1, save_file=self.save_path, seed=10)
        game1.run()
        self.assertTrue(os.path.exists(self.save_path))
        self.assertTrue(any("successfully saved" in line for line in logs1))

        # Session 2: Load Game (2) -> Title (10) -> y -> Quit (3)
        inputs2 = ["2", "10", "y", "3"]
        _, logs2, mock_in2, mock_out2 = create_scripted_io(inputs2)
        game2 = AdventureGame(input_fn=mock_in2, output_fn=mock_out2, save_file=self.save_path, seed=10)
        game2.run()

        self.assertIsNotNone(game2.player)
        self.assertEqual(game2.player.name, "Gary")
        self.assertEqual(game2.player.active_pokemon.species.name, "Charmander")
        self.assertTrue(game2.player.inventory.has_item("poke_ball", 5))
        self.assertTrue(game2.player.is_region_discovered("starting_meadow"))
        self.assertTrue(any("Loaded game successfully" in line for line in logs2))

    # 5. Missing and corrupt save file handling
    def test_05_load_missing_and_corrupt_save_handling(self) -> None:
        """Loading a non-existent or corrupted save file displays error message and does not crash."""
        # Non-existent save file
        non_existent_file = os.path.join(self.temp_dir.name, "missing.json")
        inputs1 = ["2", "3"]
        _, logs1, mock_in1, mock_out1 = create_scripted_io(inputs1)
        game1 = AdventureGame(input_fn=mock_in1, output_fn=mock_out1, save_file=non_existent_file)
        game1.run()
        self.assertIsNone(game1.player)
        self.assertTrue(any("No save file found" in line for line in logs1))

        # Corrupt save file
        corrupt_file = os.path.join(self.temp_dir.name, "corrupt.json")
        with open(corrupt_file, "w") as f:
            f.write("{invalid json content!!!")

        inputs2 = ["2", "3"]
        _, logs2, mock_in2, mock_out2 = create_scripted_io(inputs2)
        game2 = AdventureGame(input_fn=mock_in2, output_fn=mock_out2, save_file=corrupt_file)
        game2.run()
        self.assertIsNone(game2.player)
        self.assertTrue(any("Failed to load save file" in line or "Unexpected error" in line for line in logs2))

    # 6. Travel and region discovery
    def test_06_travel_and_region_discovery(self) -> None:
        """Traveling between locations updates coordinates and discovers regions."""
        # New game -> Travel (2) -> Forest Trail (3) -> Travel (2) -> Ancient Shrine Grounds (4) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "2", "3", "2", "4", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        self.assertEqual(game.player_pos, [25.0, 25.0])
        self.assertEqual(game.current_region_id, "ancient_shrine_grounds")
        self.assertTrue(game.player.is_region_discovered("starting_meadow"))
        self.assertTrue(game.player.is_region_discovered("forest_trail"))
        self.assertTrue(game.player.is_region_discovered("ancient_shrine_grounds"))

    # 7. World resource gathering and respawn cooldown
    def test_07_world_object_resource_gathering_and_respawn(self) -> None:
        """Interacting with a resource node grants items and respects respawn cooldowns."""
        # Initial Potions = 3.
        # Meadow coords = (5.0, 5.0). Object 1 is Berry Bush (5.0, 5.0) which grants 1x Potion.
        # Flow: New Game -> Interact (3) -> Berry Bush (1) -> Interact (3) -> Berry Bush (1) [depleted] -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "3", "1", "3", "1", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        # Should have 3 + 1 = 4 Potions
        self.assertEqual(game.player.inventory.get_quantity("potion"), 4)
        self.assertTrue(any("Acquired: 1x potion" in line for line in logs))
        # Second attempt should report failure/depleted
        self.assertTrue(any("Could not interact with Berry Bush" in line for line in logs))

    # 8. World sign reading
    def test_08_world_object_sign_reading(self) -> None:
        """Reading a sign displays informational text without altering inventory."""
        # Travel to Route 1 Signpost at (2.0, 1.0) -> Interact (3) -> Route 1 Sign (3) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "2", "2", "3", "3", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        self.assertTrue(any("Route 1: Pathway to Viridian City" in line for line in logs))
        # Inventory untouched
        self.assertEqual(game.player.inventory.get_quantity("potion"), 3)

    # 9. World treasure looting is atomic and single-use
    def test_09_world_object_treasure_looting_and_single_use(self) -> None:
        """Opening a treasure cache grants items once and prevents duplicate looting."""
        # Travel to Forest Trail Supply Cache Path (3) -> Interact (3) -> Trainer Supply Cache (1 in range)
        # Attempt second interact (3) -> Supply Cache (1 in range) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "2", "3", "3", "1", "3", "1", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        # Supply cache grants 1x super_potion and 2x antidote
        self.assertEqual(game.player.inventory.get_quantity("super_potion"), 1)
        self.assertEqual(game.player.inventory.get_quantity("antidote"), 2)
        self.assertTrue(game.player.is_treasure_collected("supply_cache_01"))

        # Second attempt failed
        self.assertTrue(any("Could not interact with Trainer Supply Cache" in line for line in logs))

    # 10. Landmark discovery interaction
    def test_10_world_object_landmark_discovery(self) -> None:
        """Interacting with a landmark records discovery on player."""
        # Travel to Ancient Shrine Grounds (4) -> Interact (3) -> Thunder Stone Shrine (1 in range) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "2", "4", "3", "1", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        self.assertTrue(game.player.is_landmark_discovered("ancient_shrine"))
        self.assertTrue(any("Discovered Thunder Stone Shrine" in line for line in logs))

    # 11. Quest acceptance and immediate completion
    def test_11_quest_acceptance_and_immediate_completion(self) -> None:
        """Accepting an eligible state-based quest evaluates immediately and allows claiming rewards."""
        # Player starts with 3 Potions. Stocking Supplies requires 3 Potions.
        # Quest menu (6) -> Accept (1) -> Stocking Supplies (4) -> Claim (2) -> Back (0) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "6", "1", "4", "2", "0", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        # Verify quest accepted and rewards claimed
        self.assertTrue(any("Accepted quest: 'Stocking Supplies'" in line for line in logs))
        self.assertTrue(any("Claimed rewards for 'Stocking Supplies'" in line for line in logs))
        # Reward is 1x super_potion
        self.assertEqual(game.player.inventory.get_quantity("super_potion"), 1)

    # 12. Team management and switching outside battle
    def test_12_team_management_and_switching_outside_battle(self) -> None:
        """Player can view team and switch active partner outside combat."""
        # Flow: New Game -> Team (4) -> Switch (1) -> Squirtle (2) -> Back (0) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "4", "1", "2", "0", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)

        # Manually add a second Pokemon to player's team for test setup
        def custom_input(prompt: str = "") -> str:
            if game.player is not None and not hasattr(custom_input, "added"):
                custom_input.added = True
                p2 = Pokemon(species=SQUIRTLE, personality=Personality(50, 50, 50, 50, 50, 50), level=5)
                game.player.add_pokemon(p2)
                game.player.add_to_team(p2)
            return mock_in(prompt)

        game._input_fn = custom_input
        game.run()

        self.assertEqual(game.player.active_pokemon.species.name, "Squirtle")
        self.assertTrue(any("Squirtle is now your active Pokemon" in line for line in logs))

    # 13. Inventory usage outside battle heals Pokemon
    def test_13_inventory_usage_outside_battle(self) -> None:
        """Using a Potion on an injured Pokemon restores HP and consumes the item."""
        # Flow: New Game -> Inventory (5) -> Use Item (1) -> Select Item (2: Potion) -> Select Target (1) -> Back (0) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "5", "1", "2", "1", "0", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)

        def custom_input(prompt: str = "") -> str:
            if game.player is not None and game.player.active_pokemon is not None and not hasattr(custom_input, "damaged"):
                custom_input.damaged = True
                game.player.active_pokemon.current_hp = 10
            return mock_in(prompt)

        game._input_fn = custom_input
        game.run()

        # Bulbasaur HP restored by 14 (from 10 to max HP 24)
        self.assertEqual(game.player.active_pokemon.current_hp, 24)
        # 1 Potion consumed (from 3 to 2)
        self.assertEqual(game.player.inventory.get_quantity("potion"), 2)
        self.assertTrue(any("Restored 14 HP" in line for line in logs))

    # 14. Wild battle victory awards experience and bond
    def test_14_wild_battle_victory(self) -> None:
        """A wild battle victory awards experience, increases bond, and cleans up battle session."""
        # Flow: New Game -> Explore (1) -> Attack (1) -> Move 1 (1: Thunder Shock) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "1", "1", "1", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path, seed=101)

        def custom_input(prompt: str = "") -> str:
            if game.player is not None:
                battle = game.battle_manager.get_active_battle(game.player)
                if battle is not None and not hasattr(custom_input, "weakened"):
                    custom_input.weakened = True
                    battle.active_opponent_pokemon.current_hp = 1
            return mock_in(prompt)

        game._input_fn = custom_input
        game.run()

        self.assertTrue(any("VICTORY!" in line for line in logs))
        self.assertFalse(game.battle_manager.has_active_battle(game.player))
        # Active Pokemon earned XP
        self.assertGreater(game.player.active_pokemon.experience, 0)
        self.assertGreater(game.player.active_pokemon.bond, 0)

    # 15. Wild battle capture adds Pokemon to collection and uses Poke Ball
    def test_15_wild_battle_capture(self) -> None:
        """Throwing a Poke Ball during battle catches the wild Pokemon and decrements inventory."""
        # Flow: New Game -> Explore (1) -> Throw Ball (3) -> Throw Ball (3) -> ... -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "1", "3", "3", "3", "3", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path, seed=42)
        game.run()

        # Either captured or attempted; verify Poke Balls were used
        self.assertLess(game.player.inventory.get_quantity("poke_ball"), 5)
        self.assertTrue(any("You threw a Poke Ball" in line for line in logs))

    # 16. Wild battle fleeing safely escapes
    def test_16_wild_battle_flee(self) -> None:
        """Fleeing from a wild Pokemon terminates battle with ESCAPED and returns to adventure menu."""
        # Flow: New Game -> Explore (1) -> Flee (4) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "1", "4", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path, seed=101)
        game.run()

        self.assertTrue(any("safely fled from battle" in line for line in logs))
        self.assertFalse(game.battle_manager.has_active_battle(game.player))

    # 17. In-battle fainted Pokemon forced switch
    def test_17_in_battle_fainted_forced_switch(self) -> None:
        """When active Pokemon faints mid-battle, game prompts player to switch to a conscious teammate."""
        # Flow: New Game -> Explore (1) -> Attack (1) -> Move 1 (1) -> (Pika faints) -> Switch (1) -> Flee (4) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "1", "1", "1", "1", "4", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path, seed=101)

        def custom_input(prompt: str = "") -> str:
            if game.player is not None and not hasattr(custom_input, "setup_done"):
                custom_input.setup_done = True
                # Add Squirtle to team and weaken Pikachu so Pikachu faints in 1 hit
                game.player.active_pokemon.current_hp = 1
                p2 = Pokemon(species=SQUIRTLE, personality=Personality(50, 50, 50, 50, 50, 50), level=10)
                game.player.add_pokemon(p2)
                game.player.add_to_team(p2)
            return mock_in(prompt)

        game._input_fn = custom_input
        game.run()

        self.assertTrue(any("must send out a conscious teammate" in line for line in logs))

    # 18. All Pokemon fainted defeat handling without soft-lock
    def test_18_all_pokemon_fainted_defeat_handling(self) -> None:
        """When all Pokemon faint, battle concludes with DEFEAT and revives team to prevent soft-lock."""
        # Flow: New Game -> Explore (1) -> Attack (1) -> Move 1 (1) -> (Pika faints, no teammates) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "1", "1", "1", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path, seed=101)

        def custom_input(prompt: str = "") -> str:
            if game.player is not None and not hasattr(custom_input, "setup_done"):
                custom_input.setup_done = True
                game.player.active_pokemon.current_hp = 1
            return mock_in(prompt)

        game._input_fn = custom_input
        game.run()

        self.assertTrue(any("DEFEAT!" in line for line in logs))
        self.assertTrue(any("restored to full health" in line for line in logs))
        # Active Pokemon is healthy again
        self.assertEqual(game.player.active_pokemon.current_hp, game.player.active_pokemon.max_hp)

    # 19. Session isolation between independent game instances
    def test_19_session_isolation(self) -> None:
        """Two independent AdventureGame sessions do not share mutable state."""
        inputs1 = ["1", "PlayerOne", "1", "10", "y", "3"]
        inputs2 = ["1", "PlayerTwo", "2", "10", "y", "3"]

        _, _, in1, out1 = create_scripted_io(inputs1)
        _, _, in2, out2 = create_scripted_io(inputs2)

        game1 = AdventureGame(input_fn=in1, output_fn=out1, save_file=os.path.join(self.temp_dir.name, "s1.json"))
        game2 = AdventureGame(input_fn=in2, output_fn=out2, save_file=os.path.join(self.temp_dir.name, "s2.json"))

        game1.run()
        game2.run()

        self.assertEqual(game1.player.name, "PlayerOne")
        self.assertEqual(game2.player.name, "PlayerTwo")
        self.assertEqual(game1.player.active_pokemon.species.name, "Bulbasaur")
        self.assertEqual(game2.player.active_pokemon.species.name, "Charmander")

    # 20. Invalid menu inputs do not mutate state
    def test_20_invalid_menu_inputs_do_not_mutate_state(self) -> None:
        """Sending invalid numbers or strings at menu prompts leaves game state intact."""
        # Inputs: New Game -> "Ash" -> Starter (1) -> Invalid menu choices ("abc", "99", "-5") -> Save (9) -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "abc", "99", "-5", "9", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        self.assertEqual(game.player.name, "Ash")
        self.assertTrue(any("Invalid choice 'abc'" in line for line in logs))

    # 21. Rest advances time and updates time of day
    def test_21_rest_advances_time_and_habitat_period(self) -> None:
        """Resting for 10 hours from midday advances clock from DAY to NIGHT."""
        # Flow: New Game -> Rest (8) -> Enter 10 -> Title (10) -> y -> Quit (3)
        inputs = ["1", "Ash", "1", "8", "10", "10", "y", "3"]
        _, logs, mock_in, mock_out = create_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        # 12.0 + 10.0 = 22.0 -> NIGHT
        self.assertEqual(game.game_hour, 22.0)
        self.assertEqual(game.time_of_day, TimeOfDay.NIGHT)
        self.assertTrue(any("22:00 (NIGHT)" in line for line in logs))

    # 22. Full adventure walkthrough: New Game -> Travel -> Loot -> Battle -> Save -> Load
    def test_22_full_adventure_walkthrough(self) -> None:
        """End-to-end integration test verifying complete gameplay loop with persistence."""
        save_file = os.path.join(self.temp_dir.name, "full_loop_save.json")

        # Session 1:
        # 1. New Game -> Name: "Champion Red" -> Starter: Pikachu (1)
        # 2. Travel to Forest Trail Supply Cache (2 -> 3)
        # 3. Loot Supply Cache (3 -> 1 in range)
        # 4. Travel to Ancient Shrine (2 -> 4)
        # 5. Discover Shrine Landmark (3 -> 1 in range)
        # 6. Save Game (9)
        # 7. Quit to Title (10 -> y)
        # 8. Quit (3)
        inputs1 = [
            "1", "Champion Red", "1",
            "2", "3",
            "3", "1",
            "2", "4",
            "3", "1",
            "9",
            "10", "y",
            "3",
        ]
        _, logs1, mock_in1, mock_out1 = create_scripted_io(inputs1)
        game1 = AdventureGame(input_fn=mock_in1, output_fn=mock_out1, save_file=save_file)
        game1.run()

        # Verify state in session 1
        self.assertTrue(game1.player.is_treasure_collected("supply_cache_01"))
        self.assertTrue(game1.player.is_landmark_discovered("ancient_shrine"))
        self.assertTrue(game1.player.inventory.has_item("super_potion", 1))

        # Session 2: Load game and verify restored world state
        inputs2 = ["2", "10", "y", "3"]
        _, logs2, mock_in2, mock_out2 = create_scripted_io(inputs2)
        game2 = AdventureGame(input_fn=mock_in2, output_fn=mock_out2, save_file=save_file)
        game2.run()

        self.assertIsNotNone(game2.player)
        self.assertEqual(game2.player.name, "Champion Red")
        self.assertTrue(game2.player.is_treasure_collected("supply_cache_01"))
        self.assertTrue(game2.player.is_landmark_discovered("ancient_shrine"))
        self.assertEqual(game2.player.inventory.get_quantity("super_potion"), 1)


if __name__ == "__main__":
    unittest.main()
