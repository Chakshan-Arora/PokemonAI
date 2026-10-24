"""
Unit tests for TrainerManager, in-world trainer rosters, rematch mechanics,
and persistent serialization.
"""
import unittest
import tempfile
import os
from pathlib import Path

from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.models.trainer_manager import (
    TrainerManager,
    create_default_trainers,
    create_default_trainer_manager,
)
from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.data.species import PIKACHU, BULBASAUR
from src.data.attacks import TACKLE, THUNDER_SHOCK


class TestTrainerManager(unittest.TestCase):
    """Test suite for TrainerManager."""

    def setUp(self) -> None:
        self.personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )
        self.player = Player(name="Red")
        self.pikachu = Pokemon(species=PIKACHU, personality=self.personality, level=15, attacks=[THUNDER_SHOCK])
        self.player.add_pokemon(self.pikachu)
        self.player.add_to_team(self.pikachu)
        self.player.set_active_pokemon(self.pikachu)

        self.manager = TrainerManager(seed=42)

    def test_trainer_registration_and_lookup(self) -> None:
        """Trainers can be registered, retrieved by ID, and queried by region."""
        trainer = Trainer(
            trainer_id="youngster_joey",
            name="Joey",
            title="Youngster Joey",
            region_id="starting_meadow",
        )
        self.manager.register_trainer(trainer)

        self.assertEqual(self.manager.get_trainer("youngster_joey"), trainer)
        self.assertEqual(self.manager.get_trainer("YOUNGSTER_JOEY"), trainer)
        self.assertIsNone(self.manager.get_trainer("non_existent"))

        meadow_trainers = self.manager.get_trainers_in_region("starting_meadow")
        self.assertEqual(len(meadow_trainers), 1)
        self.assertEqual(meadow_trainers[0], trainer)

        # Unregister
        self.assertTrue(self.manager.unregister_trainer("youngster_joey"))
        self.assertIsNone(self.manager.get_trainer("youngster_joey"))

    def test_prepare_trainer_battle_generates_team_once(self) -> None:
        """prepare_trainer_battle generates a valid team and preserves it on repeated calls."""
        trainer = Trainer(
            trainer_id="camper_chris",
            name="Chris",
            title="Camper Chris",
            region_id="forest_trail",
        )
        self.manager.register_trainer(trainer)
        self.assertFalse(trainer.has_team)

        prepared = self.manager.prepare_trainer_battle("camper_chris", self.player)
        self.assertTrue(prepared.has_team)
        initial_team_ids = [p.unique_id for p in prepared.team]

        # Second call preserves the exact same instances
        prepared2 = self.manager.prepare_trainer_battle("camper_chris", self.player)
        self.assertEqual([p.unique_id for p in prepared2.team], initial_team_ids)

    def test_rematch_lifecycle_rules(self) -> None:
        """Rematches require prior defeat and explicit eligibility flag."""
        trainer = Trainer(
            trainer_id="ace_trainer_kira",
            name="Kira",
            title="Ace Trainer Kira",
            difficulty=DifficultyProfile.HARD,
            region_id="tall_grass_plains",
        )
        self.manager.register_trainer(trainer)
        self.manager.prepare_trainer_battle("ace_trainer_kira", self.player)

        # 1. Cannot rematch an undefeated trainer
        ok, msg, _ = self.manager.request_rematch("ace_trainer_kira", self.player)
        self.assertFalse(ok)
        self.assertIn("not been defeated", msg)

        # Record player victory
        trainer.record_defeat()
        self.assertTrue(trainer.is_defeated)

        # 2. Cannot rematch if rematch_available is False
        ok, msg, _ = self.manager.request_rematch("ace_trainer_kira", self.player)
        self.assertFalse(ok)
        self.assertIn("not ready", msg)

        # 3. Enable rematch and challenge
        self.manager.enable_rematch("ace_trainer_kira")
        self.assertTrue(trainer.rematch_available)

        # Faint a trainer pokemon to test healing
        trainer.team[0].take_damage(trainer.team[0].max_hp)
        self.assertTrue(trainer.team[0].is_fainted)

        ok, msg, rematched = self.manager.request_rematch("ace_trainer_kira", self.player, rescale_team=True)
        self.assertTrue(ok)
        self.assertIn("Rematch challenge accepted", msg)
        self.assertFalse(rematched.rematch_available)
        self.assertFalse(rematched.team[0].is_fainted)
        self.assertEqual(rematched.team[0].current_hp, rematched.team[0].max_hp)

    def test_serialization_and_deserialization_round_trip(self) -> None:
        """TrainerManager serializes all registered trainers and deserializes them cleanly."""
        trainer = Trainer(
            trainer_id="gym_leader_brock",
            name="Brock",
            title="Gym Leader Brock",
            archetype=TrainerArchetype.GYM_LEADER,
            difficulty=DifficultyProfile.BOSS,
            region_id="mountain_pass",
            reward_items={"max_potion": 1},
        )
        self.manager.register_trainer(trainer)
        self.manager.prepare_trainer_battle("gym_leader_brock", self.player)
        trainer.record_defeat()
        trainer.claim_rewards(self.player)

        data = self.manager.to_dict()
        restored_manager = TrainerManager.from_dict(data)

        restored_trainer = restored_manager.get_trainer("gym_leader_brock")
        self.assertIsNotNone(restored_trainer)
        self.assertEqual(restored_trainer.name, "Brock")
        self.assertTrue(restored_trainer.is_defeated)
        self.assertEqual(restored_trainer.defeat_count, 1)
        self.assertTrue(restored_trainer.reward_claimed)
        self.assertTrue(restored_trainer.has_team)
        self.assertEqual(len(restored_trainer.team), len(trainer.team))

    def test_save_and_load_from_file(self) -> None:
        """TrainerManager persists to and loads from disk atomically."""
        trainer = Trainer(
            trainer_id="youngster_joey",
            name="Joey",
            title="Youngster Joey",
            region_id="starting_meadow",
        )
        self.manager.register_trainer(trainer)
        self.manager.prepare_trainer_battle("youngster_joey", self.player)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "trainers_save.json"
            self.manager.save_to_file(filepath)
            self.assertTrue(filepath.exists())

            loaded_manager = TrainerManager.load_from_file(filepath)
            loaded_joey = loaded_manager.get_trainer("youngster_joey")
            self.assertIsNotNone(loaded_joey)
            self.assertEqual(loaded_joey.name, "Joey")
            self.assertTrue(loaded_joey.has_team)

    def test_create_default_trainer_manager(self) -> None:
        """Default trainer manager includes canonical trainers across world regions."""
        default_manager = create_default_trainer_manager()
        trainers = default_manager.list_trainers()
        self.assertGreaterEqual(len(trainers), 8)

        # Check canonical trainers exist
        joey = default_manager.get_trainer("youngster_joey")
        brock = default_manager.get_trainer("gym_leader_brock")
        kira = default_manager.get_trainer("ace_trainer_kira")

        self.assertIsNotNone(joey)
        self.assertEqual(joey.difficulty, DifficultyProfile.EASY)
        self.assertIsNotNone(brock)
        self.assertEqual(brock.difficulty, DifficultyProfile.BOSS)
        self.assertIsNotNone(kira)
        self.assertEqual(kira.difficulty, DifficultyProfile.HARD)


if __name__ == "__main__":
    unittest.main()
