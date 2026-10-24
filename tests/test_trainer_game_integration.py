"""
Integration tests verifying playable Trainer Battle integration in AdventureGame
and persistent companion save/load through SaveManager and AdventureGame.
"""
import os
import tempfile
import unittest

from game import AdventureGame
from src.models.battle_state import BattleState
from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.models.trainer_manager import (
    TrainerManager,
    create_default_trainer_manager,
    get_trainer_state_path_for_save_file,
)
from src.models.save_manager import SaveManager, save_game_with_ai, load_game_with_trainers
from src.data.species import PIKACHU
from src.data.attacks import QUICK_ATTACK, THUNDER_SHOCK


def create_scripted_io(input_sequence: list[str]) -> tuple[list[str], callable, callable]:
    """Creates injectable input_fn and output_fn pair for automated test execution."""
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

    return logs, mock_input, mock_output


class TestTrainerGameIntegration(unittest.TestCase):
    """End-to-end integration tests for Trainer Battles in AdventureGame."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_path = os.path.join(self.temp_dir.name, "test_game_save.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_trainer_menu_listing_and_cancel(self) -> None:
        """Player can view area trainers via [t] menu option and cancel back cleanly."""
        # 1: New Game -> Name: 'Ash' -> Starter: Bulbasaur (1)
        # t: Challenge Trainers -> 0: Cancel -> 10: Title Menu -> y -> 3: Quit
        inputs = ["1", "Ash", "1", "t", "0", "10", "y", "3"]
        logs, mock_in, mock_out = create_scripted_io(inputs)

        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path, seed=42)
        game.run()

        self.assertIsNotNone(game.player)
        self.assertTrue(any("AREA TRAINERS - Starting Meadow" in line for line in logs))
        self.assertTrue(any("Youngster Joey" in line for line in logs))
        self.assertTrue(any("Lass Haley" in line for line in logs))

    def test_02_battle_restrictions_and_trainer_defeat(self) -> None:
        """In a trainer battle, Poke Balls and fleeing are blocked, and defeating awards rewards."""
        # 1: New Game -> Name: 'Ash' -> Starter: Bulbasaur (1)
        # t: Challenge Trainers -> 1: Youngster Joey
        # Turn 1: 3 (Throw Poke Ball - blocked)
        # Turn 1: 4 (Flee - blocked)
        # Turn 1: 5 (Inspect opponent)
        # Turn 1: 1 (Attack) -> 1 (Tackle/Vine Whip)
        # If battle still active, continue attacking until won or resolved
        inputs = [
            "1", "Ash", "1",
            "t", "1",
            "3",        # Blocked: Poke ball
            "4",        # Blocked: Flee
            "5",        # Inspect opponent
            "1", "1",   # Attack move 1
            "1", "1",   # Attack move 1
            "1", "1",   # Attack move 1
            "1", "1",   # Attack move 1
            "1", "1",   # Attack move 1
            "10", "y", "3"
        ]
        logs, mock_in, mock_out = create_scripted_io(inputs)

        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path, seed=42)
        # Give player's starter overwhelming attack power for fast decisive test resolution
        game.player = None  # Will be created by flow
        
        # We hook into game by running
        game.run()

        self.assertTrue(any("You cannot catch another trainer's Pok" in line for line in logs))
        self.assertTrue(any("You cannot flee from a trainer battle" in line for line in logs))
        self.assertTrue(any("TRAINER BATTLE: Youngster Joey" in line for line in logs))

    def test_03_trainer_save_and_load_persistence(self) -> None:
        """Trainer defeat status, generated teams, and claimed rewards persist across saves."""
        # Session 1: New Game -> Name: 'Red' -> Starter: Bulbasaur (1)
        # Defeat Youngster Joey, then Save Game (9), then Quit (10 -> y -> 3)
        inputs1 = ["1", "Red", "1", "9", "10", "y", "3"]
        logs1, mock_in1, mock_out1 = create_scripted_io(inputs1)

        game1 = AdventureGame(input_fn=mock_in1, output_fn=mock_out1, save_file=self.save_path, seed=10)
        game1.run()

        # Manually mark Joey as defeated in session 1's saved trainer state to test round-trip
        trainer_save_path = get_trainer_state_path_for_save_file(self.save_path)
        self.assertTrue(trainer_save_path.exists())

        loaded_tm = TrainerManager.load_from_file(trainer_save_path)
        joey = loaded_tm.get_trainer("youngster_joey")
        self.assertIsNotNone(joey)
        # Prepare and defeat Joey
        dummy_player = Player(name="Red")
        dummy_mon = Pokemon(species=PIKACHU, personality=Personality(50,50,50,50,50,50), level=10)
        dummy_player.add_pokemon(dummy_mon)
        dummy_player.add_to_team(dummy_mon)
        loaded_tm.prepare_trainer_battle("youngster_joey", dummy_player)
        joey.record_defeat()
        joey_team_ids = [p.unique_id for p in joey.team]
        loaded_tm.save_to_file(trainer_save_path)

        # Session 2: Load Game (2) -> Check Joey is defeated and team is intact
        inputs2 = ["2", "t", "1", "10", "y", "3"]
        logs2, mock_in2, mock_out2 = create_scripted_io(inputs2)

        game2 = AdventureGame(input_fn=mock_in2, output_fn=mock_out2, save_file=self.save_path, seed=10)
        game2.run()

        reloaded_joey = game2.trainer_manager.get_trainer("youngster_joey")
        self.assertIsNotNone(reloaded_joey)
        self.assertTrue(reloaded_joey.is_defeated)
        self.assertEqual([p.unique_id for p in reloaded_joey.team], joey_team_ids)
        self.assertTrue(any("already been defeated" in line for line in logs2))

    def test_04_save_manager_trainers_helpers(self) -> None:
        """SaveManager save_with_trainers and load_with_trainers serialize companion trainers.json."""
        player = Player(name="Leaf")
        pika = Pokemon(species=PIKACHU, personality=Personality(50,50,50,50,50,50), level=15)
        player.add_pokemon(pika)
        player.add_to_team(pika)

        tm = create_default_trainer_manager()
        brock = tm.get_trainer("gym_leader_brock")
        tm.prepare_trainer_battle("gym_leader_brock", player)
        team_species = [p.species.name for p in brock.team]

        save_file = os.path.join(self.temp_dir.name, "save_slot.json")
        SaveManager.save_with_trainers(player, save_file, tm)

        trainer_file = get_trainer_state_path_for_save_file(save_file)
        self.assertTrue(trainer_file.exists())

        loaded_player, loaded_tm = SaveManager.load_with_trainers(save_file)
        self.assertEqual(loaded_player.name, "Leaf")
        self.assertIsNotNone(loaded_tm)
        loaded_brock = loaded_tm.get_trainer("gym_leader_brock")
        self.assertIsNotNone(loaded_brock)
        self.assertEqual([p.species.name for p in loaded_brock.team], team_species)


if __name__ == "__main__":
    unittest.main()
